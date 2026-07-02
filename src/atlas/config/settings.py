"""Central configuration via environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AtlasSettings(BaseSettings):
    """All configuration in one place — never hardcode secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ATLAS_",
        extra="ignore",
    )

    data_path: Path = Field(default=Path("./data"))
    log_level: str = "INFO"
    log_format: str = "json"
    channels: str = "book,ticker,trades"
    interval: str = "100ms"
    futures_count: int = 3

    # Deribit-specific (loaded without ATLAS_ prefix via nested or direct env)
    deribit_api_key: str = Field(default="", validation_alias="DERIBIT_API_KEY")
    deribit_api_secret: str = Field(default="", validation_alias="DERIBIT_API_SECRET")
    deribit_environment: str = Field(default="production", validation_alias="DERIBIT_ENVIRONMENT")

    @property
    def channel_list(self) -> list[str]:
        return [c.strip() for c in self.channels.split(",") if c.strip()]
