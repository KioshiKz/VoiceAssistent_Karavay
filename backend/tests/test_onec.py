import unittest
import uuid
from unittest.mock import Mock, patch

from app.services.onec_service import NoRedirect, ODataReader, OneCError, OneCSessionLimit, summarize


def row(index):
    return {"Ref_Key": str(uuid.UUID(int=index + 1)), "Description": "Item", "DeletionMark": False}


class OneCReaderTests(unittest.TestCase):
    def reader(self, *pages):
        reader = ODataReader("http://localhost/test/", "test", "")
        reader.request = Mock(side_effect=pages)
        return reader

    def test_pagination_preserves_deleted_records_for_local_validation(self):
        first = [row(i) for i in range(200)]
        first[0]["DeletionMark"] = True
        reader = self.reader({"odata.count": "201", "value": first}, {"odata.count": "201", "value": [row(200)]})
        result = reader.read_entity("units")
        self.assertEqual(len(result), 201)
        self.assertTrue(result[0]["DeletionMark"])
        self.assertEqual(reader.request.call_args.args[1]["$skip"], 200)
        self.assertNotIn("$filter", reader.request.call_args.args[1])

    def test_truncated_page_is_not_a_complete_snapshot(self):
        with self.assertRaises(OneCError):
            self.reader({"odata.count": "201", "value": [row(0)]}).read_entity("units")

    def test_changed_count_rejects_mixed_snapshot(self):
        reader = self.reader({"odata.count": "201", "value": [row(i) for i in range(200)]}, {"odata.count": "202", "value": [row(200), row(201)]})
        with self.assertRaises(OneCError):
            reader.read_entity("units")

    def test_repeated_page_rejected(self):
        reader = self.reader({"odata.count": "201", "value": [row(i) for i in range(200)]}, {"odata.count": "201", "value": [row(0)]})
        with self.assertRaises(OneCError):
            reader.read_entity("units")

    def test_string_boolean_rejected(self):
        value = {**row(0), "DeletionMark": "false"}
        with self.assertRaises(OneCError):
            self.reader({"odata.count": "1", "value": [value]}).read_entity("units")

    def test_session_limit_is_retried(self):
        reader = ODataReader("http://localhost/test/", "test", "")
        reader.request_once = Mock(side_effect=[OneCSessionLimit("limit"), {"value": []}])
        with patch("app.services.onec_service.time.sleep") as sleep:
            self.assertEqual(reader.request("Catalog_X", {}), {"value": []})
        self.assertEqual(reader.request_once.call_count, 2)
        sleep.assert_called_once()

    def test_session_limit_gives_up_eventually(self):
        reader = ODataReader("http://localhost/test/", "test", "")
        reader.request_once = Mock(side_effect=OneCSessionLimit("limit"))
        with patch("app.services.onec_service.time.sleep"), self.assertRaises(OneCSessionLimit):
            reader.request("Catalog_X", {})

    def test_credentials_not_forwarded_on_redirect(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_report_excludes_deleted_items_and_flags_missing_unit(self):
        records = {"units": [], "kinds": [], "items": [
            {**row(0), "IsFolder": False},
            {**row(1), "IsFolder": False, "DeletionMark": True},
            {**row(2), "IsFolder": True},
        ]}
        result = summarize(records)
        self.assertEqual(result["active_items"], 1)
        self.assertEqual(result["items_without_active_unit"], 1)


if __name__ == "__main__":
    unittest.main()
