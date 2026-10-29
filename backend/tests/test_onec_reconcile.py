import unittest
from datetime import datetime

from app.services.onec_reconcile_service import reconcile

WH = "11111111-1111-1111-1111-111111111111"
END = datetime(2026, 11, 1)


def report(ref, lines, date="2026-10-10T10:00:00", posted=True, not_reflected=False):
    return {"Ref_Key": ref, "Number": f"R{ref[-1]}", "Date": date, "Posted": posted, "DeletionMark": False,
            "СкладСырья_Key": WH, "НеОтражатьВОтчетахПоСырью": not_reflected,
            "Продукция": [{"Номенклатура_Key": product, "Спецификация_Key": spec, "Количество": qty, "Коэффициент": 1}
                          for product, spec, qty in lines]}


def requisition(ref, lines, base=None, base_type="Document_ОтчетПроизводстваЗаСмену", date="2026-10-10T19:00:00"):
    return {"Ref_Key": ref, "Number": f"Q{ref[-1]}", "Date": date, "Posted": True, "DeletionMark": False,
            "Склад_Key": WH, "ДокументОснование": base or "", "ДокументОснование_Type": f"StandardODATA.{base_type}",
            "Материалы": [{"Номенклатура_Key": m, "Количество": q, "Коэффициент": 1} for m, q in lines]}


RECORDS = {
    "items": [{"Ref_Key": "flour", "Description": "Мука", "Code": "1", "БазоваяЕдиницаИзмерения_Key": "kg"},
              {"Ref_Key": "bread", "Description": "Хлеб", "Code": "2", "БазоваяЕдиницаИзмерения_Key": "pcs"}],
    "units": [{"Ref_Key": "kg", "Description": "кг"}, {"Ref_Key": "pcs", "Description": "шт"}],
    "specs": [{"Ref_Key": "spec", "Количество": 100, "IsFolder": False,
               "ИсходныеКомплектующие": [{"Номенклатура_Key": "flour", "Количество": 20}]}],
    "warehouses": [{"Ref_Key": WH, "Description": "Хлебный цех"}],
}


class ReconcileTests(unittest.TestCase):
    def test_norm_from_spec_and_fact_split_by_source(self):
        result = reconcile(
            [report("rep1", [("bread", "spec", 150)])],
            [requisition("req1", [("flour", 30)], base="rep1"),
             requisition("req2", [("flour", 2.5)], base_type="Document_АктПриемаПередачи")],
            RECORDS, END)
        [row] = result["rows"]
        self.assertEqual((row["warehouse"], row["material"], row["unit"]), ("Хлебный цех", "Мука", "кг"))
        self.assertEqual((row["norm"], row["fact_by_report"], row["fact_by_act"], row["fact"]), (30.0, 30.0, 2.5, 32.5))
        self.assertAlmostEqual(row["diff_pct"], 8.333, places=3)
        self.assertEqual(result["report_deviations"], [])

    def test_missing_requisition_spec_and_per_report_deviation(self):
        result = reconcile(
            [report("rep1", [("bread", "spec", 100)]), report("rep2", [("bread", "spec", 100), ("bread", "nospec", 5)])],
            [requisition("req1", [("flour", 25)], base="rep1")],
            RECORDS, END)
        self.assertEqual([r["number"] for r in result["reports_without_requisition"]], ["R2"])
        self.assertEqual(len(result["lines_without_spec"]), 1)
        [deviation] = result["report_deviations"]
        self.assertEqual(deviation["top"][0], {"material": "Мука", "unit": "кг", "norm": 20.0, "fact": 25.0})

    def test_costs_from_postings_price_norm_and_deviation(self):
        def posting(doc, line, qty, amount):
            return {"Recorder": doc, "Recorder_Type": "StandardODATA.Document_ТребованиеНакладная", "LineNumber": str(line),
                    "ExtDimensionCr1": "flour", "ExtDimensionCr2": WH, "Сумма": amount, "КоличествоCr": qty}

        result = reconcile(
            [report("rep1", [("bread", "spec", 100)])],
            # 25 kg written off: 20 kg at 150 ₸/kg in two batches, 5 kg with no cost (negative stock).
            [requisition("req1", [("flour", 25)], base="rep1")],
            RECORDS, END,
            [posting("req1", 1, 15, 2250), posting("req1", 2, 5, 750), posting("req1", 3, 5, 0)])
        [row] = result["rows"]
        self.assertEqual((row["price"], row["fact_cost"], row["zero_cost_qty"]), (150.0, 3000.0, 5.0))
        self.assertEqual((row["norm_cost"], row["diff_cost"]), (3000.0, 750.0))
        self.assertEqual(result["costs"], {"fact": 3000.0, "norm": 3000.0, "diff": 750.0, "zero_cost_rows": 1,
                                           "incomplete_requisitions": []})

    def test_requisition_with_uncovered_lines_has_no_cost(self):
        result = reconcile(
            [report("rep1", [("bread", "spec", 100)])],
            [requisition("req1", [("flour", 20)], base="rep1")],
            RECORDS, END,
            [{"Recorder": "req1", "Recorder_Type": "StandardODATA.Document_ТребованиеНакладная", "LineNumber": "1",
              "ExtDimensionCr1": "flour", "ExtDimensionCr2": WH, "Сумма": 1500, "КоличествоCr": 10}])
        [row] = result["rows"]
        self.assertEqual((row["fact_cost"], row["price"], row["diff_cost"]), (0.0, None, None))
        self.assertEqual(result["costs"]["incomplete_requisitions"], ["Q1"])

    def test_without_postings_quantities_only(self):
        result = reconcile([report("rep1", [("bread", "spec", 100)])], [], RECORDS, END)
        self.assertIsNone(result["costs"])
        self.assertNotIn("price", result["rows"][0])

    def test_unposted_not_reflected_and_late_requisitions(self):
        result = reconcile(
            [report("rep1", [("bread", "spec", 100)], posted=False),
             report("rep2", [("bread", "spec", 100)], not_reflected=True),
             report("rep3", [("bread", "spec", 100)], date="2026-10-31T10:00:00")],
            # Dated after the period: links rep3 but is not counted as this period's write-off.
            [requisition("req1", [("flour", 20)], base="rep3", date="2026-11-01T08:00:00")],
            RECORDS, END)
        self.assertEqual(result["reports"], 2)
        self.assertEqual(result["reports_not_reflected"], 1)
        self.assertEqual(result["reports_without_requisition"], [])
        [row] = result["rows"]
        self.assertEqual((row["norm"], row["fact"]), (20.0, 0.0))


if __name__ == "__main__":
    unittest.main()
