from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    username: str = Field(..., alias="USERNAME")
    password: str = Field(..., alias="PASSWORD")
    output_path: str = Field(...)
