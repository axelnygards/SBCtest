from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./fut.db"
    redis_url: str | None = None
    season: str = "fc27"
    ruleset: str = "fc27"
    source_ea_ratings_enabled: bool = True
    source_futbin_enabled: bool = False
    ea_ratings_mode: str = "auto"          # auto | api | site
    ea_ratings_refresh_hours: int = 24
    price_live_window_min: int = 60        # observations newer than this count as "live"
    price_stale_window_h: int = 6          # older live prices are still used, flagged stale
    cors_origins: list[str] = ["http://localhost:5173", "chrome-extension://*"]


settings = Settings()
