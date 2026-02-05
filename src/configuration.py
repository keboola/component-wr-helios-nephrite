import logging

from keboola.component.exceptions import UserException
from pydantic import BaseModel, Field, ValidationError, field_validator


class FieldMapping(BaseModel):
    source_column: str
    destination_field: str
    data_type: str | None = None
    enabled: bool = True


class RowConfiguration(BaseModel):
    entity_name: str
    folder_id: int | None = None
    field_mapping: list[FieldMapping] = Field(default_factory=list)


class Configuration(BaseModel):
    api_url: str
    username: str = Field(alias="#username")
    password: str = Field(alias="#password")
    default_folder_id: int | None = None
    debug: bool = False

    def __init__(self, **data):
        try:
            super().__init__(**data)
        except ValidationError as e:
            error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise UserException(f"Configuration Error: {', '.join(error_messages)}")

        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, v):
        if not v.startswith("http"):
            raise ValueError("API URL must start with http:// or https://")
        return v.rstrip("/")
