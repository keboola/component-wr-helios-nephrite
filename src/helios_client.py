import base64
import logging
import os

import requests
from keboola.component.exceptions import UserException


class HeliosClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._auth_credentials: tuple[str, str] | None = None

    def _get_auth_header(self) -> dict:
        if not self._auth_credentials:
            raise UserException("Not authenticated. Call login() first.")

        username, user_id = self._auth_credentials
        credentials = f"{username}:{user_id}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def login(self, username: str, password: str) -> dict:
        url = f"{self.base_url}/api/Connect/LogIn"
        payload = {"userName": username, "password": password}

        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise UserException(f"Authentication failed: {e}")

        data = response.json()

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
            self.session.post(url, headers=self._get_auth_header())
            logging.info("Successfully logged out")
        except requests.exceptions.RequestException as e:
            logging.warning(f"Logout request failed: {e}")
        finally:
            self._auth_credentials = None

    def upload_file(self, file_path: str, folder_id: int | None = None) -> str:
        url = f"{self.base_url}/api/v1/Files/Upload"
        if folder_id:
            url += f"?folderId={folder_id}"

        headers = self._get_auth_header()
        filename = os.path.basename(file_path)

        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "text/csv")}
                response = self.session.post(url, headers=headers, files=files)
                response.raise_for_status()
        except FileNotFoundError:
            raise UserException(f"File not found: {file_path}")
        except requests.exceptions.RequestException as e:
            raise UserException(f"File upload failed: {e}")

        data = response.json()

        if "fileUID" not in data:
            raise UserException(f"File upload failed: No fileUID in response. Response: {data}")

        logging.info(f"Successfully uploaded file {filename}, fileUID: {data['fileUID']}")
        return data["fileUID"]

    def general_import(
        self,
        import_id: int,
        file_uid: str,
        data_source: str = "S",
        target_folder_id: int | None = None,
        transaction_scope: str | None = None,
        error_limit: int | None = None,
    ) -> dict:
        url = f"{self.base_url}/api/v1/DataTransfers/GeneralImport/{import_id}"
        url += f"?fileUID={file_uid}"

        headers = self._get_auth_header()
        headers["Content-Type"] = "application/json"

        params_item = {"dataSource": data_source}

        if target_folder_id is not None:
            params_item["targetFolderId"] = target_folder_id

        if transaction_scope:
            params_item["transactionScope"] = transaction_scope

        if error_limit is not None:
            params_item["errorLimit"] = error_limit

        payload = {"params": [params_item]}

        try:
            response = self.session.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text
            raise UserException(f"GeneralImport failed: {e}. Details: {error_detail}")

        data = response.json()
        logging.info(f"GeneralImport completed for import_id={import_id}")

        return data

    def browse_entity(self, entity_name: str, folder_id: int | None = None, top: int = 1) -> dict:
        url = f"{self.base_url}/api/v1/Generic/browse/{entity_name}?Top={top}"
        if folder_id:
            url += f"&FolderId={folder_id}"

        headers = self._get_auth_header()

        try:
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text
            raise UserException(f"Failed to browse entity '{entity_name}': {e}. Details: {error_detail}")

        data = response.json()

        if "columnsInfo" not in data:
            raise UserException(
                f"Browse entity '{entity_name}' returned unexpected format. "
                f"Expected 'columnsInfo' field. Response: {data}"
            )

        logging.info(f"Successfully browsed entity '{entity_name}', found {len(data['columnsInfo'])} fields")
        return data

    def create_entity(self, entity_name: str, data: dict, folder_id: int | None = None) -> dict:
        url = f"{self.base_url}/api/v1/Generic/{entity_name}"
        if folder_id:
            url += f"?folderId={folder_id}"

        headers = self._get_auth_header()
        headers["Content-Type"] = "application/json"

        try:
            response = self.session.post(url, headers=headers, json=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text
            raise UserException(f"Failed to create entity '{entity_name}': {e}. Details: {error_detail}")

        result = response.json()
        logging.debug(f"Successfully created entity '{entity_name}': {result}")
        return result
