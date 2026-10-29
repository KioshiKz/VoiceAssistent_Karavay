import unittest
from decimal import Decimal

from app.services.onec_import_service import build_plan, digest
from app.services.onec_service import current_main_specs

EMPTY = "00000000-0000-0000-0000-000000000000"
KG, PCS, METER = "u-kg", "u-pcs", "u-m"


def item(ref, name, unit=PCS, parent=EMPTY, deleted=False, folder=False):
    return {"Ref_Key": ref, "Description": name, "DeletionMark": deleted, "IsFolder": folder,
            "Parent_Key": parent, "БазоваяЕдиницаИзмерения_Key": unit}


def spec(ref, owner, yield_, lines, deleted=False):
    return {"Ref_Key": ref, "Owner_Key": owner, "Количество": yield_, "DeletionMark": deleted, "IsFolder": False,
            "ИсходныеКомплектующие": [{"LineNumber": str(n), "Номенклатура_Key": key, "Количество": qty} for n, key, qty in lines]}


def records(items, specs, mains):
    return {
        "units": [{"Ref_Key": KG, "Code": "166      ", "Description": "кг"},
                  {"Ref_Key": PCS, "Code": "796      ", "Description": "шт"},
                  {"Ref_Key": METER, "Code": "006      ", "Description": "м"}],
        "items": items,
        "specs": specs,
        "main_specs": [{"Номенклатура_Key": product, "СпецификацияНоменклатуры_Key": s} for product, s in mains],
    }


class BuildPlanTests(unittest.TestCase):
    def test_piece_recipe_converted_to_canonical_units_in_line_order(self):
        data = records(
            [item("g", "Хлеба", folder=True), item("bread", "Хлеб  ржаной", parent="g"),
             item("flour", "Мука", KG), item("film", "Плёнка", METER)],
            [spec("s1", "bread", 100, [(2, "film", 5), (1, "flour", 22.8)])],
            [("bread", "s1")],
        )
        plan = build_plan(data)
        [product] = plan["products"]
        self.assertEqual(product["name"], "Хлеб ржаной")
        self.assertEqual(product["groups"], ["Хлеба"])
        self.assertEqual(product["base_quantity"], 100)
        self.assertEqual(product["steps"], [{"ingredient_ref": "flour", "quantity": Decimal("22800.000")}])
        self.assertEqual(plan["ingredients"][0]["measure_type"], "weight")
        self.assertEqual(plan["skipped_lines"][0]["count"], 1)

    def test_unsupported_recipes_are_reported_not_imported(self):
        data = records(
            [item("old", "Удаленные", folder=True), item("retired", "Старый", parent="old"),
             item("tape", "Лента", METER), item("bun", "Булка"), item("gone", "Удалён", deleted=True),
             item("flour", "Мука", KG)],
            [spec("s1", "retired", 10, [(1, "flour", 1)]), spec("s2", "tape", 1, [(1, "flour", 1)]),
             spec("s3", "gone", 10, [(1, "flour", 1)]), spec("s4", "bun", 2.5, [(1, "flour", 1)])],
            [("retired", "s1"), ("tape", "s2"), ("gone", "s3"), ("bun", "s4")],
        )
        plan = build_plan(data)
        self.assertEqual(plan["products"], [])
        self.assertEqual({r["reason"] for r in plan["skipped"]}, {
            "Продукция в группе «Удаленные» 1С", "Выход в «м», а не в штуках или килограммах",
            "Продукция удалена или не найдена в 1С", "Выход в штуках не целый"})

    def test_kilogram_recipe_keeps_fractional_yield(self):
        data = records([item("cream", "Крем", KG), item("butter", "Масло", KG)],
                       [spec("s1", "cream", 1.8, [(1, "butter", 0.9)])], [("cream", "s1")])
        [product] = build_plan(data)["products"]
        self.assertEqual((product["base_quantity"], product["yield_unit"]), (1.8, "kg"))
        self.assertEqual(product["steps"], [{"ingredient_ref": "butter", "quantity": Decimal("900.000")}])

    def test_piece_recipe_hash_is_stable_across_versions(self):
        # Links stored before kilogram support must still match piece recipes.
        data = records([item("bread", "Хлеб"), item("flour", "Мука", KG)],
                       [spec("s1", "bread", 100, [(1, "flour", 1)])], [("bread", "s1")])
        [product] = build_plan(data)["products"]
        self.assertEqual(product["hash"], digest([100, [["flour", Decimal("1000.000")]]]))

    def test_recipe_hash_tracks_quantities(self):
        base = [item("bread", "Хлеб"), item("flour", "Мука", KG)]
        first = build_plan(records(base, [spec("s1", "bread", 100, [(1, "flour", 1)])], [("bread", "s1")]))
        second = build_plan(records(base, [spec("s1", "bread", 100, [(1, "flour", 2)])], [("bread", "s1")]))
        self.assertNotEqual(first["products"][0]["hash"], second["products"][0]["hash"])


class MainSpecTests(unittest.TestCase):
    def test_latest_started_period_wins(self):
        rows = [
            {"Period": "2026-01-01T00:00:00", "Номенклатура_Key": "a", "СпецификацияНоменклатуры_Key": "old"},
            {"Period": "2026-09-30T00:00:00", "Номенклатура_Key": "a", "СпецификацияНоменклатуры_Key": "current"},
            {"Period": "2027-01-01T00:00:00", "Номенклатура_Key": "a", "СпецификацияНоменклатуры_Key": "future"},
        ]
        [row] = current_main_specs(rows, "2026-10-30")
        self.assertEqual(row["СпецификацияНоменклатуры_Key"], "current")


if __name__ == "__main__":
    unittest.main()
