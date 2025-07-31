# Type stubs for pydantic_settings
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

def SettingsConfigDict(*, case_sensitive: bool = ..., extra: str = ..., **kwargs: Any) -> ConfigDict: ...  # noqa: N802

T = TypeVar("T", bound="BaseSettings")

class BaseSettings(BaseModel):
    pass
