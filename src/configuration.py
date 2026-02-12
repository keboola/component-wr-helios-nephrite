from pydantic import BaseModel, Field, field_validator


class FieldMapping(BaseModel):
    source_column: str
    destination_field: str


class Connection(BaseModel):
    api_url: str
    username: str = Field(alias="#username")
    password: str = Field(alias="#password")
    default_folder_id: int | None = None

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, v):
        if not v.startswith("http"):
            raise ValueError("API URL must start with http:// or https://")
        return v.rstrip("/")


class Configuration(BaseModel):
    connection: Connection
    entity_name: str
    folder_id: int | None = None
    field_mapping: list[FieldMapping] = Field(default_factory=list)
    debug: bool = False
