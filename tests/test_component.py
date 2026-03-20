import os
import unittest
from unittest.mock import MagicMock, patch

from component import Component
from configuration import Configuration, Connection
from helios_client import HeliosClient


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

    def test_no_match_included_with_empty_destination(self):
        result = self.comp._auto_match_fields(
            ["unrelated_column"],
            [{"field_name": "documentNumber", "data_type": "string", "header_text": "Doc Number"}],
        )
        self.assertEqual(result, [{"source_column": "unrelated_column", "destination_field": ""}])

    def test_field_with_none_name_skipped(self):
        result = self.comp._auto_match_fields(
            ["id"],
            [{"field_name": None, "data_type": "string", "header_text": "ID"}],
        )
        self.assertEqual(result, [{"source_column": "id", "destination_field": ""}])


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


class TestRunValidation(unittest.TestCase):
    def test_run_raises_when_no_field_mappings(self):
        comp = _make_component()
        comp.params = Configuration(
            connection=_make_connection(),
            entity_name="invoices",
            field_mapping=[],
        )
        comp.client = MagicMock()

        from keboola.component.exceptions import UserException

        with self.assertRaises(UserException):
            comp.run()


class TestHeliosClient(unittest.TestCase):
    def _make_client(self) -> HeliosClient:
        client = HeliosClient("https://api.helios.example.com")
        client._auth_credentials = ("testuser", "user-id-123")
        return client

    def test_login_success(self):
        client = HeliosClient("https://api.helios.example.com")
        mock_response = MagicMock()
        mock_response.json.return_value = {"userId": "user-id-123", "userName": "testuser"}

        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            result = client.login("testuser", "secret")

        mock_post.assert_called_once()
        self.assertEqual(result["userId"], "user-id-123")
        self.assertEqual(client._auth_credentials, ("testuser", "user-id-123"))

    def test_login_missing_user_id_raises(self):
        client = HeliosClient("https://api.helios.example.com")
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "bad credentials"}

        from keboola.component.exceptions import UserException

        with patch.object(client.session, "post", return_value=mock_response):
            with self.assertRaises(UserException):
                client.login("testuser", "wrong")

    def test_login_non_json_response_raises(self):
        client = HeliosClient("https://api.helios.example.com")
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.status_code = 200
        mock_response.text = "<html>Error</html>"

        from keboola.component.exceptions import UserException

        with patch.object(client.session, "post", return_value=mock_response):
            with self.assertRaises(UserException):
                client.login("testuser", "secret")

    def test_browse_entity_success(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"columnsInfo": [{"columnName": "docNo"}]}

        with patch.object(client.session, "get", return_value=mock_response):
            result = client.browse_entity("invoices")

        self.assertIn("columnsInfo", result)

    def test_browse_entity_missing_columns_info_raises(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "data"}

        from keboola.component.exceptions import UserException

        with patch.object(client.session, "get", return_value=mock_response):
            with self.assertRaises(UserException):
                client.browse_entity("invoices")

    def test_create_entity_success(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 42}

        with patch.object(client.session, "post", return_value=mock_response):
            result = client.create_entity("invoices", {"docNo": "INV-001"})

        self.assertEqual(result["id"], 42)

    def test_create_entity_http_error_raises(self):
        client = self._make_client()

        import requests as req
        from keboola.component.exceptions import UserException

        http_error = req.exceptions.HTTPError(response=MagicMock(json=MagicMock(return_value={"error": "bad"})))

        with patch.object(client.session, "post", side_effect=http_error):
            with self.assertRaises(UserException):
                client.create_entity("invoices", {"docNo": "INV-001"})


if __name__ == "__main__":
    unittest.main()
