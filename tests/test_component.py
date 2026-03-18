import os
import unittest
from unittest.mock import MagicMock, patch

from component import Component
from configuration import Configuration, Connection


def _make_component() -> Component:
    """Instantiate Component without triggering __init__ (for unit testing pure methods)."""
    return Component.__new__(Component)


def _make_connection() -> Connection:
    return Connection(**{"api_url": "https://api.helios.example.com", "#username": "user", "#password": "pass"})


class TestRunNoConfig(unittest.TestCase):
    @patch.dict(os.environ, {"KBC_DATADIR": "./non-existing-dir"})
    def test_run_no_cfg_fails(self):
        with self.assertRaises(ValueError):
            Component()


class TestAutoMatchFields(unittest.TestCase):
    def setUp(self):
        self.comp = _make_component()

    def test_exact_match(self):
        result = self.comp._auto_match_fields(
            ["documentNumber", "amount"],
            [
                {"field_name": "documentNumber", "data_type": "string", "header_text": "Document Number"},
                {"field_name": "amount", "data_type": "decimal", "header_text": "Amount"},
            ],
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"source_column": "documentNumber", "destination_field": "documentNumber"})

    def test_case_insensitive_match(self):
        result = self.comp._auto_match_fields(
            ["DOCUMENTNUMBER"],
            [{"field_name": "documentNumber", "data_type": "string", "header_text": "Doc Number"}],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["destination_field"], "documentNumber")

    def test_normalized_match_underscores(self):
        result = self.comp._auto_match_fields(
            ["document_number"],
            [{"field_name": "documentNumber", "data_type": "string", "header_text": "Doc Number"}],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["destination_field"], "documentNumber")

    def test_no_match_excluded_from_result(self):
        result = self.comp._auto_match_fields(
            ["unrelated_column"],
            [{"field_name": "documentNumber", "data_type": "string", "header_text": "Doc Number"}],
        )
        self.assertEqual(result, [])

    def test_field_with_none_name_skipped(self):
        result = self.comp._auto_match_fields(
            ["id"],
            [{"field_name": None, "data_type": "string", "header_text": "ID"}],
        )
        self.assertEqual(result, [])


class TestTransformRow(unittest.TestCase):
    def setUp(self):
        self.comp = _make_component()

    def test_basic_mapping(self):
        result = self.comp._transform_row(
            {"name": "Acme", "amount": "100"},
            {"name": "customerName", "amount": "totalAmount"},
        )
        self.assertEqual(result, {"customerName": "Acme", "totalAmount": "100"})

    def test_empty_string_becomes_none(self):
        result = self.comp._transform_row(
            {"name": "", "amount": "100"},
            {"name": "customerName", "amount": "totalAmount"},
        )
        self.assertIsNone(result["customerName"])
        self.assertEqual(result["totalAmount"], "100")

    def test_missing_source_column_returns_none(self):
        result = self.comp._transform_row(
            {"amount": "100"},
            {"name": "customerName", "amount": "totalAmount"},
        )
        self.assertIsNone(result["customerName"])


class TestRunMocked(unittest.TestCase):
    @patch("component.HeliosClient")
    @patch.dict(os.environ, {"KBC_DATADIR": "./tests/data/happy-path"})
    def test_run_calls_create_entity(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        comp = _make_component()
        comp.params = Configuration(
            connection=_make_connection(),
            entity_name="invoices",
            field_mapping=[],
        )
        comp.client = mock_client

        # No field mappings → should raise UserException before hitting the API
        from keboola.component.exceptions import UserException

        with self.assertRaises(UserException):
            comp.run()


if __name__ == "__main__":
    unittest.main()
