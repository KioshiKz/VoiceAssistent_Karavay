"""Transfer current 1C main specifications into application products and recipes.

Reads only the local snapshot in `onec_records`; nothing is sent to 1C. Orders
and execution history are never touched. A preview runs the same transfer and
rolls it back, so its report matches what a real run would do.
"""
from decimal import Decimal
import hashlib
import json
import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.models.ingredient import Ingredient
from app.models.onec import OneCLink, OneCRecord
from app.models.product import Product
from app.models.recipe_step import RecipeStep
from app.services.folder_service import _build_path
from app.services.onec_service import OneCBusy, OneCError
from app.services.unit_conversion import quantize_quantity

EMPTY_REF = "00000000-0000-0000-0000-000000000000"
# OKEI unit codes -> application measure type and factor to canonical units.
UNITS = {
    "163": ("weight", Decimal(1)),
    "166": ("weight", Decimal(1000)),
    "168": ("weight", Decimal(1000000)),
    "111": ("volume", Decimal(1)),
    "112": ("volume", Decimal(1000)),
    "796": ("count", Decimal(1)),
}
PIECE_UNIT, KILOGRAM_UNIT = "796", "166"
# Product yield units the application supports, by OKEI code.
YIELD_UNITS = {PIECE_UNIT: "pcs", KILOGRAM_UNIT: "kg"}
ROOT_FOLDER, PRODUCTS_FOLDER, INGREDIENTS_FOLDER = "1С", "Продукция", "Сырьё"


class OneCImportError(OneCError):
    pass


class Reasons:
    """Counts per reason with a few example names for the report."""

    def __init__(self):
        self.items = {}

    def add(self, reason, name):
        entry = self.items.setdefault(reason, {"reason": reason, "count": 0, "examples": []})
        entry["count"] += 1
        if len(entry["examples"]) < 5 and name not in entry["examples"]:
            entry["examples"].append(name)

    def report(self):
        return sorted(self.items.values(), key=lambda entry: -entry["count"])


def clean_name(value):
    return " ".join(value.split())[:255] or "Без названия"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def group_names(item, items):
    names, ref = [], item["Parent_Key"]
    while ref in items and ref != EMPTY_REF and len(names) < 20:
        names.append(clean_name(items[ref]["Description"]))
        ref = items[ref]["Parent_Key"]
    return names[::-1]


def build_plan(records):
    """Pure part: decide which 1C recipes can be transferred and how."""
    items = {r["Ref_Key"]: r for r in records.get("items", [])}
    unit_codes = {r["Ref_Key"]: r["Code"].strip() for r in records.get("units", [])}
    unit_names = {r["Ref_Key"]: r["Description"].strip() for r in records.get("units", [])}
    specs = {r["Ref_Key"]: r for r in records.get("specs", [])}
    skipped, skipped_lines, warnings = Reasons(), Reasons(), Reasons()
    products, ingredients = [], {}

    for main in records.get("main_specs", []):
        item = items.get(main["Номенклатура_Key"])
        spec = specs.get(main["СпецификацияНоменклатуры_Key"])
        name = clean_name(item["Description"]) if item else main["Номенклатура_Key"]
        if item is None or item["DeletionMark"] or item["IsFolder"]:
            reason = "Продукция удалена или не найдена в 1С"
        elif any(group.lower().startswith("удален") for group in group_names(item, items)):
            reason = "Продукция в группе «Удаленные» 1С"
        elif spec is None or spec["DeletionMark"] or spec["IsFolder"]:
            reason = "Основная спецификация удалена или не найдена"
        elif spec["Owner_Key"] != item["Ref_Key"]:
            reason = "Спецификация принадлежит другой позиции"
        elif unit_codes.get(item["БазоваяЕдиницаИзмерения_Key"]) not in YIELD_UNITS:
            reason = f"Выход в «{unit_names.get(item['БазоваяЕдиницаИзмерения_Key'], '?')}», а не в штуках или килограммах"
        elif quantize_quantity(Decimal(str(spec["Количество"]))) <= 0:
            reason = "Выход не положительный"
        elif unit_codes[item["БазоваяЕдиницаИзмерения_Key"]] == PIECE_UNIT and not float(spec["Количество"]).is_integer():
            reason = "Выход в штуках не целый"
        else:
            reason = None
        if reason:
            skipped.add(reason, name)
            continue

        steps, broken = [], False
        for line in sorted(spec["ИсходныеКомплектующие"], key=lambda line: int(line["LineNumber"])):
            component = items.get(line["Номенклатура_Key"])
            if component is None or component["IsFolder"]:
                broken = True
                break
            component_name = clean_name(component["Description"])
            unit_key = component["БазоваяЕдиницаИзмерения_Key"]
            unit = UNITS.get(unit_codes.get(unit_key))
            if unit is None:
                skipped_lines.add(f"Единица «{unit_names.get(unit_key, '?')}» не переносится", component_name)
                continue
            quantity = quantize_quantity(Decimal(str(line["Количество"])) * unit[1])
            if quantity <= 0:
                skipped_lines.add("Нулевое количество", component_name)
                continue
            if component["DeletionMark"]:
                warnings.add("Компонент помечен на удаление в 1С", component_name)
            ingredients[component["Ref_Key"]] = {
                "ref": component["Ref_Key"],
                "name": component_name,
                "measure_type": unit[0],
                "groups": group_names(component, items),
            }
            steps.append({"ingredient_ref": component["Ref_Key"], "quantity": quantity})
        if broken:
            skipped.add("Компонент не найден в 1С", name)
        elif not steps:
            skipped.add("Нет переносимых строк состава", name)
        else:
            yield_unit = YIELD_UNITS[unit_codes[item["БазоваяЕдиницаИзмерения_Key"]]]
            lines = [[s["ingredient_ref"], s["quantity"]] for s in steps]
            if yield_unit == "pcs":
                base_quantity = int(spec["Количество"])
                # Unchanged form for piece recipes, so their earlier links still match.
                recipe_hash = digest([base_quantity, lines])
            else:
                base_quantity = float(quantize_quantity(Decimal(str(spec["Количество"]))))
                recipe_hash = digest(["kg", base_quantity, lines])
            products.append({
                "ref": item["Ref_Key"],
                "name": name,
                "base_quantity": base_quantity,
                "yield_unit": yield_unit,
                "groups": group_names(item, items),
                "steps": steps,
                "hash": recipe_hash,
            })

    return {
        "products": products,
        "ingredients": list(ingredients.values()),
        "skipped": skipped.report(),
        "skipped_lines": skipped_lines.report(),
        "warnings": warnings.report(),
    }


def local_recipe_hash(steps):
    """Fingerprint of a product's recipe as stored in the application."""
    return digest([
        [s.step_type, s.ingredient_id, quantize_quantity(s.quantity_canonical) if s.quantity_canonical is not None else None,
         s.event_template_id, s.event_params]
        for s in sorted(steps, key=lambda s: s.order_index)
    ])


async def load_snapshot(db: AsyncSession, source: str):
    records = {}
    rows = (await db.execute(select(OneCRecord.entity, OneCRecord.data).where(OneCRecord.source == source))).all()
    for entity, data in rows:
        records.setdefault(entity, []).append(data)
    return records


class FolderTree:
    """Get-or-create folders by name below a workshop."""

    def __init__(self, db, workshop, user_id):
        self.db, self.workshop, self.user_id = db, workshop, user_id
        self.cache, self.created = {}, 0

    async def get(self, names):
        parent = self.workshop
        for name in names:
            key = (parent.id, name)
            if key not in self.cache:
                folder = (await self.db.execute(
                    select(Folder).where(Folder.parent_id == parent.id, Folder.name == name)
                )).scalar_one_or_none()
                if folder is None:
                    folder_id = uuid.uuid4()
                    folder = Folder(id=folder_id, name=name, parent_id=parent.id, depth=parent.depth + 1,
                                    materialized_path=_build_path(parent.materialized_path, folder_id),
                                    created_by=self.user_id)
                    self.db.add(folder)
                    self.created += 1
                self.cache[key] = folder
            parent = self.cache[key]
        return parent


def new_steps(product_id, plan_product, ingredient_ids):
    return [
        RecipeStep(id=uuid.uuid4(), product_id=product_id, order_index=index, step_type="ingredient",
                   ingredient_id=ingredient_ids[step["ingredient_ref"]], quantity_canonical=step["quantity"])
        for index, step in enumerate(plan_product["steps"])
    ]


async def import_recipes(db: AsyncSession, source: str, workshop_id: uuid.UUID, user_id: uuid.UUID, *, dry_run: bool):
    if not (await db.execute(text("SELECT pg_try_advisory_xact_lock(791463022)"))).scalar():
        raise OneCBusy("Перенос из 1С уже выполняется.")
    try:
        workshop = await db.get(Folder, workshop_id)
        if workshop is None or workshop.parent_id is not None:
            raise OneCImportError("Выберите цех верхнего уровня.")
        records = await load_snapshot(db, source)
        if not records.get("specs") or not records.get("main_specs"):
            raise OneCImportError("В загруженных данных нет спецификаций. Сначала синхронизируйте 1С.")
        plan = build_plan(records)
        result = await apply_plan(db, source, plan, FolderTree(db, workshop, user_id))
        if dry_run:
            await db.rollback()
        else:
            await db.commit()
        return {"dry_run": dry_run, **result}
    except BaseException:
        await db.rollback()
        raise


async def apply_plan(db, source, plan, folders):
    links = {
        (link.entity, str(link.ref)): link
        for link in (await db.execute(select(OneCLink).where(OneCLink.source == source))).scalars()
    }
    targets = [link.target_id for link in links.values()]
    existing_ingredients = {i.id: i for i in (await db.execute(select(Ingredient).where(Ingredient.id.in_(targets)))).scalars()}
    existing_products = {p.id: p for p in (await db.execute(select(Product).where(Product.id.in_(targets)))).scalars()}
    current_steps = {}
    for step in (await db.execute(select(RecipeStep).where(RecipeStep.product_id.in_(list(existing_products))))).scalars():
        current_steps.setdefault(step.product_id, []).append(step)

    stats = {"products_created": 0, "products_updated": 0, "products_unchanged": 0, "products_reactivated": 0,
             "products_deactivated": 0, "ingredients_created": 0, "ingredients_updated": 0, "steps_written": 0}
    conflicts, ingredient_ids = Reasons(), {}

    def link_for(entity, ref, target_id):
        link = links.get((entity, ref))
        if link is None:
            link = OneCLink(source=source, entity=entity, ref=uuid.UUID(ref), target_id=target_id)
            db.add(link)
            links[(entity, ref)] = link
        link.target_id = target_id
        return link

    for planned in plan["ingredients"]:
        link = links.get(("ingredient", planned["ref"]))
        ingredient = existing_ingredients.get(link.target_id) if link else None
        if ingredient is None:
            folder = await folders.get([ROOT_FOLDER, INGREDIENTS_FOLDER, *planned["groups"]])
            ingredient = Ingredient(id=uuid.uuid4(), folder_id=folder.id, name=planned["name"],
                                    measure_type=planned["measure_type"], is_active=True)
            db.add(ingredient)
            link_for("ingredient", planned["ref"], ingredient.id)
            stats["ingredients_created"] += 1
        elif ingredient.measure_type != planned["measure_type"]:
            conflicts.add("Мера ингредиента в приложении не совпадает с единицей 1С", ingredient.name)
            continue
        elif ingredient.name != planned["name"]:
            ingredient.name = planned["name"]
            stats["ingredients_updated"] += 1
        ingredient_ids[planned["ref"]] = ingredient.id

    planned_refs = set()
    for planned in plan["products"]:
        planned_refs.add(planned["ref"])
        if any(step["ingredient_ref"] not in ingredient_ids for step in planned["steps"]):
            conflicts.add("Есть ингредиент с несовпадающей мерой", planned["name"])
            continue
        link = links.get(("product", planned["ref"]))
        product = existing_products.get(link.target_id) if link else None
        if link is not None and product is None:
            conflicts.add("Продукт удалён в приложении вручную", planned["name"])
            continue
        if product is None:
            folder = await folders.get([ROOT_FOLDER, PRODUCTS_FOLDER, *planned["groups"]])
            product = Product(id=uuid.uuid4(), folder_id=folder.id, name=planned["name"],
                              base_quantity=planned["base_quantity"], yield_unit=planned["yield_unit"], is_active=True)
            db.add(product)
            steps = new_steps(product.id, planned, ingredient_ids)
            db.add_all(steps)
            link = link_for("product", planned["ref"], product.id)
            link.source_hash, link.local_hash = planned["hash"], local_recipe_hash(steps)
            stats["products_created"] += 1
            stats["steps_written"] += len(steps)
            continue

        if not product.is_active:
            product.is_active = True
            stats["products_reactivated"] += 1
        renamed = product.name != planned["name"]
        product.name = planned["name"]
        if link.source_hash == planned["hash"]:
            stats["products_updated" if renamed else "products_unchanged"] += 1
            continue
        if local_recipe_hash(current_steps.get(product.id, [])) != link.local_hash:
            # Someone edited the recipe here; never overwrite manual work.
            conflicts.add("Рецептура изменена и в 1С, и в приложении", planned["name"])
            continue
        await db.execute(delete(RecipeStep).where(RecipeStep.product_id == product.id))
        steps = new_steps(product.id, planned, ingredient_ids)
        db.add_all(steps)
        product.base_quantity = planned["base_quantity"]
        product.yield_unit = planned["yield_unit"]
        link.source_hash, link.local_hash = planned["hash"], local_recipe_hash(steps)
        stats["products_updated"] += 1
        stats["steps_written"] += len(steps)

    # Recipes no longer current in 1C stay in the application but are hidden from use.
    for (entity, ref), link in links.items():
        product = existing_products.get(link.target_id)
        if entity == "product" and ref not in planned_refs and product is not None and product.is_active:
            product.is_active = False
            stats["products_deactivated"] += 1

    await db.flush()
    return {
        **stats,
        "folders_created": folders.created,
        "candidates": len(plan["products"]),
        "skipped": plan["skipped"],
        "skipped_lines": plan["skipped_lines"],
        "warnings": plan["warnings"],
        "conflicts": conflicts.report(),
    }
