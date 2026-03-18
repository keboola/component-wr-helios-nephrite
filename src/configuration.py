from pydantic import BaseModel, ConfigDict, Field, field_validator


class FieldMapping(BaseModel):
    source_column: str
    destination_field: str


class Connection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    api_url: str
    username: str = Field(alias="#username")
    password: str = Field(alias="#password")

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("API URL must start with http:// or https://")
        return v.rstrip("/")  # normalise here so HeliosClient receives a clean URL


class Configuration(BaseModel):
    connection: Connection
    entity_name: str | None = None
    folder_id: int | None = None
    field_mapping: list[FieldMapping] = Field(default_factory=list)
    debug: bool = False
