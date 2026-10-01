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
    catalogue_refresh_s: float = 30        # in-memory card catalogue: delta reload at most this often
    solve_cache_ttl_s: int = 1800          # market-only solutions: reuse while the prices hold
    warm_presets_min: int = 15             # recompute active SBC presets in the background
    warm_platforms: list[str] = ["console", "pc"]
    solver_queue: int = 6                  # solves allowed to wait for a worker before 503
    solve_rate_per_min: int = 20           # per user / IP
    rating_report_min_reporters: int = 2   # users needed before a rating's fodder price counts
    reporter_salt: str = ""                # hashes IPs of anonymous price reporters (random if unset)
    cors_origins: list[str] = ["http://localhost:5173", "chrome-extension://*"]


settings = Settings()
if not settings.reporter_salt:
    import secrets
    settings.reporter_salt = secrets.token_hex(16)
