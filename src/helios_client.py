import base64
import logging

import requests
from keboola.component.exceptions import UserException

DEFAULT_TIMEOUT = 30


class HeliosClient:
    def __init__(self, base_url: str):
        self.base_url = base_url  # URL is already normalised by Configuration.validate_api_url
        self.session = requests.Session()
        self._auth_credentials: tuple[str, str] | None = None

    def _get_auth_header(self) -> dict:
        if not self._auth_credentials:
            raise UserException("Not authenticated. Call login() first.")

        username, user_id = self._auth_credentials
        credentials = f"{username}:{user_id}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    @staticmethod
    def _parse_json(response: requests.Response, context: str) -> dict:
        try:
            return response.json()
        except ValueError as e:
            raise UserException(
                f"{context}: expected JSON response but got {response.status_code} — {response.text[:200]}"
            ) from e

    def login(self, username: str, password: str) -> dict:
        url = f"{self.base_url}/api/Connect/LogIn"
        payload = {"userName": username, "password": password}

        try:
            response = self.session.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise UserException(f"Authentication failed: {e}") from e

        data = self._parse_json(response, "Login")

        if "userId" not in data:
            raise UserException("Authentication failed: No userId in response")

        self._auth_credentials = (data.get("userName", username), data["userId"])
        logging.info(f"Successfully authenticated as {self._auth_credentials[0]}")

        return data

    def logout(self) -> None:
        if not self._auth_credentials:
            return

        url = f"{self.base_url}/api/Connect/LogOut"
        try:
            self.session.post(url, headers=self._get_auth_header(), timeout=DEFAULT_TIMEOUT)
            logging.info("Successfully logged out")
        except requests.exceptions.RequestException as e:
            logging.warning(f"Logout request failed: {e}")
        finally:
            self._auth_credentials = None

    def browse_entity(self, entity_name: str, folder_id: int | None = None, top: int = 1) -> dict:
        url = f"{self.base_url}/api/v1/Generic/browse/{entity_name}?Top={top}"
        if folder_id is not None:
            url += f"&FolderId={folder_id}"

        headers = self._get_auth_header()

        try:
            response = self.session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text
            raise UserException(
                f"Failed to browse entity '{entity_name}': {e}. Details: {error_detail}"
            ) from e

        data = self._parse_json(response, f"Browse entity '{entity_name}'")

        if "columnsInfo" not in data:
            raise UserException(
                f"Browse entity '{entity_name}' returned unexpected format. "
                f"Expected 'columnsInfo' field. Response: {data}"
            )

        logging.info(f"Successfully browsed entity '{entity_name}', found {len(data['columnsInfo'])} fields")
        return data

    def create_entity(self, entity_name: str, data: dict, folder_id: int | None = None) -> dict:
        url = f"{self.base_url}/api/v1/Generic/{entity_name}"
        if folder_id is not None:
            url += f"?folderId={folder_id}"

        headers = self._get_auth_header()
        headers["Content-Type"] = "application/json"

        try:
            response = self.session.post(url, headers=headers, json=data, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text
            raise UserException(
                f"Failed to create entity '{entity_name}': {e}. Details: {error_detail}"
            ) from e

        result = self._parse_json(response, f"Create entity '{entity_name}'")
        logging.debug(f"Successfully created entity '{entity_name}': {result}")
        return result
