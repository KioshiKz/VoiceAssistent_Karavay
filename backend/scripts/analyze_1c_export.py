"""Validate a Karavay JSON export and report ambiguities before importing it."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path
import uuid


UNIT_FACTORS = {
    "г": ("weight", Decimal(1)), "гр": ("weight", Decimal(1)),
    "кг": ("weight", Decimal(1000)), "т": ("weight", Decimal(1000000)),
    "мл": ("volume", Decimal(1)), "л": ("volume", Decimal(1000)),
    "шт": ("count", Decimal(1)),
}


def unit_conversion(name):
    return UNIT_FACTORS.get(name.strip().lower().rstrip("."))


def index_records(records, label):
    result = {}
    for record in records:
        ref = str(uuid.UUID(record["ref"]))
        if ref in result:
            raise ValueError(f"Duplicate {label} reference: {ref}")
        result[ref] = record
    return result


def analyze(payload):
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported export schema")
    if payload.get("configuration") != "БухгалтерияДляКазахстана":
        raise ValueError("Unexpected 1C configuration")
    units = index_records(payload["units"], "unit")
    items = index_records(payload["items"], "item")
    recipes = index_records(payload["recipes"], "recipe")
    issues = []
    products = defaultdict(list)
    components = set()
    active_recipes = [r for r in recipes.values() if not r["deleted"]]
    for recipe in active_recipes:
        products[recipe["product_ref"]].append(recipe["ref"])
        product = items.get(recipe["product_ref"])
        if not product or product["deleted"] or product["is_group"]:
            issues.append({"recipe": recipe["ref"], "problem": "missing_or_inactive_product"})
        if Decimal(str(recipe["quantity"])) <= 0:
            issues.append({"recipe": recipe["ref"], "problem": "nonpositive_output_quantity"})
        if not recipe["components"]:
            issues.append({"recipe": recipe["ref"], "problem": "empty_recipe"})
        for component in recipe["components"]:
            components.add(component["item_ref"])
            item = items.get(component["item_ref"])
            if not item or item["deleted"] or item["is_group"]:
                issues.append({"recipe": recipe["ref"], "item": component["item_ref"],
                               "problem": "missing_or_inactive_component"})
            if Decimal(str(component["quantity"])) <= 0:
                issues.append({"recipe": recipe["ref"], "item": component["item_ref"],
                               "problem": "nonpositive_component_quantity"})
    used_units = Counter()
    for ref in set(products) | components:
        item = items.get(ref)
        if item is None or item["is_group"]:
            continue
        unit = units.get(item.get("unit_ref"))
        if unit is None or unit["deleted"]:
            issues.append({"item": ref, "problem": "missing_or_inactive_unit"})
            continue
        used_units[unit["name"]] += 1
        if unit_conversion(unit["name"]) is None:
            issues.append({"item": ref, "unit": unit["name"], "problem": "unknown_unit_conversion"})
    multiple = {ref: refs for ref, refs in products.items() if len(refs) > 1}
    return {
        "configuration": payload["configuration"],
        "configuration_version": payload["configuration_version"],
        "counts": {"units": len(units), "items": len(items), "recipes": len(recipes),
                   "active_recipes": len(active_recipes), "recipe_products": len(products),
                   "recipe_components": len(components), "warehouses": len(payload["warehouses"]),
                   "departments": len(payload["departments"])},
        "used_units": dict(used_units), "products_with_multiple_recipes": multiple,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.export.read_text(encoding="utf-8-sig"), parse_float=Decimal)
    report = analyze(payload)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["counts"]))
    print(f"Issues: {len(report['issues'])}; products with multiple recipes: {len(report['products_with_multiple_recipes'])}")


if __name__ == "__main__":
    main()
