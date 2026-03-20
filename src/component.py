import csv
import logging
import re

from keboola.component.base import ComponentBase, sync_action
from keboola.component.exceptions import UserException
from pydantic import ValidationError

from configuration import Configuration
from helios_client import HeliosClient


class Component(ComponentBase):
    def __init__(self):
        super().__init__()
        self._load_configuration()
        self.client = HeliosClient(self.params.connection.api_url)

    def _load_configuration(self):
        try:
            self.params = Configuration(**self.configuration.parameters)
        except ValidationError as e:
            error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise UserException(f"Configuration Error: {', '.join(error_messages)}")

    @sync_action("load_entity_fields")
    def load_entity_fields(self) -> dict:
        if not self.params.entity_name:
            raise UserException("Entity name is required")

        csv_columns = []
        input_tables = self.get_input_tables_definitions()
        if input_tables:
            table = input_tables[0]
            csv_columns = table.column_names if hasattr(table, "column_names") and table.column_names else []

            if not csv_columns and table.full_path:
                try:
                    with open(table.full_path, encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        csv_columns = reader.fieldnames or []
                except Exception as e:
                    logging.warning(f"Could not read CSV columns: {e}")

        # TODO: Remove dummy CSV columns once real input tables are available during sync actions
        if not csv_columns:
            csv_columns = ["id", "name", "description", "created_at", "updated_at"]

        # TODO: Remove dummy data and uncomment real API call once Helios API is available
        available_fields = [
            {"field_name": "id", "data_type": "integer", "header_text": "ID", "visible": True},
            {"field_name": "name", "data_type": "string", "header_text": "Name", "visible": True},
            {"field_name": "description", "data_type": "string", "header_text": "Description", "visible": True},
            {"field_name": "created_at", "data_type": "datetime", "header_text": "Created At", "visible": True},
            {"field_name": "updated_at", "data_type": "datetime", "header_text": "Updated At", "visible": True},
        ]
        # self.client.login(self.params.connection.username, self.params.connection.password)
        # try:
        #     browse_result = self.client.browse_entity(entity_name, folder_id)
        #     columns_info = browse_result.get("columnsInfo", [])
        #     available_fields = [
        #         {
        #             "field_name": col.get("columnName"),
        #             "data_type": col.get("dataTypeRepo"),
        #             "header_text": col.get("headerText"),
        #             "visible": col.get("visible", True),
        #         }
        #         for col in columns_info
        #     ]
        # finally:
        #     self.client.logout()

        field_mapping = self._auto_match_fields(csv_columns, available_fields)

        cfg_data = self.params.model_dump(exclude={"connection", "acknowledge"})
        cfg_data["field_mapping"] = field_mapping
        return {
            "type": "data",
            "data": {
                **cfg_data,
                "_metadata_": {"api_fields": available_fields},
            },
        }

    def _auto_match_fields(self, csv_columns: list[str], api_fields: list[dict]) -> list[dict]:
        def normalize(name: str) -> str:
            return re.sub(r"[_\s-]", "", name.lower())

        api_field_map = {}
        api_field_normalized = {}

        for field in api_fields:
            field_name = field.get("field_name")
            if not field_name:
                continue
            api_field_map[field_name.lower()] = field
            api_field_normalized[normalize(field_name)] = field

        suggested_mapping = []

        for csv_col in csv_columns:
            mapping = {
                "source_column": csv_col,
                "destination_field": "",
            }

            if csv_col.lower() in api_field_map:
                matched_field = api_field_map[csv_col.lower()]
                mapping["destination_field"] = matched_field.get("field_name")
            else:
                normalized = normalize(csv_col)
                if normalized in api_field_normalized:
                    matched_field = api_field_normalized[normalized]
                    mapping["destination_field"] = matched_field.get("field_name")

            suggested_mapping.append(mapping)

        return suggested_mapping

    def run(self):
        if not self.params.entity_name:
            raise UserException("Entity name is required. Please configure it in the row settings.")

        if not self.params.field_mapping:
            raise UserException(
                "No field mappings configured. Please use the 'Load Fields' button to configure field mappings."
            )

        field_map = {}
        for mapping in self.params.field_mapping:
            if mapping.destination_field:
                field_map[mapping.source_column] = mapping.destination_field

        if not field_map:
            raise UserException(
                "No valid field mappings. Please configure at least one mapping with a destination field."
            )

        input_tables = self.get_input_tables_definitions()
        if not input_tables:
            raise UserException("No input tables found. Please map at least one input table.")

        logging.info(f"Found {len(input_tables)} input table(s) to process")
        logging.info(f"Authenticating with Helios API at {self.params.connection.api_url}")

        self.client.login(self.params.connection.username, self.params.connection.password)

        try:
            for table in input_tables:
                logging.info(f"Processing table: {table.name}")
                self._process_table(table, field_map)

            logging.info("All tables processed successfully")

        finally:
            self.client.logout()

    def _process_table(self, table, field_map: dict):
        entity_name = self.params.entity_name
        folder_id = self.params.folder_id

        logging.info(f"Creating entities for '{entity_name}' with {len(field_map)} mapped fields")

        success_count = 0
        error_count = 0

        try:
            with open(table.full_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row_num, csv_row in enumerate(reader, start=1):
                    try:
                        api_payload = self._transform_row(csv_row, field_map)
                        self.client.create_entity(entity_name, api_payload, folder_id)
                        success_count += 1

                        if self.params.debug and success_count <= 3:
                            logging.debug(f"Created entity {success_count}: {api_payload}")

                    except UserException as e:
                        error_count += 1
                        logging.error(f"Row {row_num} failed: {e}")
                    except Exception as e:
                        error_count += 1
                        logging.error(f"Row {row_num} failed with unexpected error: {e}")

        except FileNotFoundError:
            raise UserException(f"Input file not found: {table.full_path}")
        except Exception as e:
            raise UserException(f"Failed to process CSV file: {e}")

        logging.info(f"Table '{table.name}' processed: {success_count} succeeded, {error_count} failed")

        if error_count > 0:
            logging.warning(f"Table '{table.name}' completed with {error_count} errors. Check logs for details.")

    def _transform_row(self, csv_row: dict, field_map: dict) -> dict:
        api_payload = {}

        for csv_column, api_field in field_map.items():
            value = csv_row.get(csv_column)

            if value == "":
                value = None

            api_payload[api_field] = value

        return api_payload


if __name__ == "__main__":
    try:
        comp = Component()
        comp.execute_action()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
