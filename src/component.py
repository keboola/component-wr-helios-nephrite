import csv
import logging
import re

from keboola.component.base import ComponentBase, sync_action
from keboola.component.exceptions import UserException

from configuration import Configuration, RowConfiguration
from helios_client import HeliosClient


class Component(ComponentBase):
    def __init__(self):
        super().__init__()
        self.params = Configuration(**self.configuration.parameters)
        self.client = HeliosClient(self.params.api_url)

    @sync_action("load_entity_fields")
    def load_entity_fields(self) -> dict:
        action_params = self.configuration.action_parameters
        entity_name = action_params.get("entity_name")

        if not entity_name:
            raise UserException("Entity name is required")

        folder_id = action_params.get("folder_id") or self.params.default_folder_id

        csv_columns = []
        input_tables = self.get_input_tables_definitions()
        if input_tables and len(input_tables) > 0:
            table = input_tables[0]
            csv_columns = table.columns if hasattr(table, "columns") and table.columns else []

            if not csv_columns and table.full_path:
                try:
                    with open(table.full_path, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        csv_columns = reader.fieldnames or []
                except Exception as e:
                    logging.warning(f"Could not read CSV columns: {e}")

        self.client.login(self.params.username, self.params.password)

        try:
            browse_result = self.client.browse_entity(entity_name, folder_id)
            columns_info = browse_result.get("columnsInfo", [])

            available_fields = []
            for col in columns_info:
                field_info = {
                    "field_name": col.get("columnName"),
                    "data_type": col.get("dataTypeRepo"),
                    "header_text": col.get("headerText"),
                    "visible": col.get("visible", True),
                }
                available_fields.append(field_info)

            suggested_mapping = self._auto_match_fields(csv_columns, available_fields)

            return {
                "type": "data",
                "data": {
                    "entity_name": entity_name,
                    "folder_id": folder_id,
                    "field_mapping": suggested_mapping,
                },
            }

        finally:
            self.client.logout()

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
                # Try normalized match
                normalized = normalize(csv_col)
                if normalized in api_field_normalized:
                    matched_field = api_field_normalized[normalized]
                    mapping["destination_field"] = matched_field.get("field_name")

            # Only include mappings that have a destination field (matched columns)
            if mapping["destination_field"]:
                suggested_mapping.append(mapping)

        return suggested_mapping

    def run(self):
        input_tables = self.get_input_tables_definitions()
        if not input_tables:
            raise UserException("No input tables found. Please map at least one input table.")

        logging.info(f"Found {len(input_tables)} input table(s) to process")

        logging.info(f"Authenticating with Helios API at {self.params.api_url}")
        self.client.login(self.params.username, self.params.password)

        try:
            for table in input_tables:
                logging.info(f"Processing table: {table.name}")
                row_config = self._get_row_configuration(table)
                self._process_table_generic(self.client, table, row_config, self.params)

            logging.info("All tables processed successfully")

        finally:
            self.client.logout()

    def _get_row_configuration(self, table) -> RowConfiguration:
        config_data = {}
        if hasattr(table, "configuration") and table.configuration:
            config_data = table.configuration

        try:
            row_config = RowConfiguration(**config_data)
        except Exception as e:
            raise UserException(f"Invalid configuration for table '{table.name}': {e}")

        if not row_config.field_mapping:
            raise UserException(
                f"No field mappings configured for table '{table.name}'. "
                f"Please use the 'Load Fields' button to configure field mappings."
            )

        return row_config

    def _process_table_generic(self, client: HeliosClient, table, row_config: RowConfiguration, params: Configuration):
        entity_name = row_config.entity_name
        folder_id = row_config.folder_id or params.default_folder_id

        field_map = {}
        for mapping in row_config.field_mapping:
            if mapping.destination_field:
                field_map[mapping.source_column] = mapping.destination_field

        if not field_map:
            raise UserException(
                f"No valid field mappings for table '{table.name}'. "
                f"Please configure at least one enabled mapping with a destination field."
            )

        logging.info(f"Creating entities for '{entity_name}' with {len(field_map)} mapped fields")

        success_count = 0
        error_count = 0

        try:
            with open(table.full_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row_num, csv_row in enumerate(reader, start=1):
                    try:
                        api_payload = self._transform_row(csv_row, field_map)
                        client.create_entity(entity_name, api_payload, folder_id)
                        success_count += 1

                        if params.debug and success_count <= 3:
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
