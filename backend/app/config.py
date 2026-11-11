"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "CivicOps AI"
    environment: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'var' / 'civicops.db').as_posix()}"
    upload_dir: str = str(BACKEND_ROOT / "var" / "uploads")
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    seed_on_startup: bool = True
    auto_create_tables: bool = True
    session_hours: int = 12
    password_iterations: int = 600_000
    max_upload_mb: int = 8
    max_image_pixels: int = 25_000_000
    public_report_rate_limit_per_hour: int = 20
    chat_rate_limit_per_hour: int = Field(default=60, ge=1, le=1000)

    duplicate_radius_m: float = 300.0
    duplicate_window_hours: int = 72
    duplicate_min_score: float = 35.0
    duplicate_max_results: int = 10

    # Spatial-temporal hotspot clustering settings.
    hotspot_radius_m: float = 150.0
    hotspot_window_days: int = 30
    hotspot_min_incidents: int = 2
    priority_hotspot_boost: float = 15.0

    # Deterministic SLA target windows (hours) by priority.
    sla_hours_critical: int = 12
    sla_hours_high: int = 24
    sla_hours_medium: int = 48
    sla_hours_low: int = 72
    sla_warning_ratio: float = 0.75
    sla_sweep_interval_seconds: int = 0
    alert_webhook_url: str | None = None

    # Deterministic priority weights. Defaults total 100 points.
    priority_weight_low: float = 10.0
    priority_weight_moderate: float = 25.0
    priority_weight_high: float = 40.0
    priority_weight_critical: float = 50.0
    priority_recurrence_step: float = 8.0
    priority_recurrence_cap: float = 25.0
    priority_age_points_cap: float = 25.0
    priority_age_cap_hours: float = 120.0
    priority_threshold_critical: float = 62.0
    priority_threshold_high: float = 42.0
    priority_threshold_medium: float = 22.0

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    ai_timeout_seconds: float = Field(default=25.0, ge=2.0, le=120.0)
    ai_max_attempts: int = Field(default=2, ge=1, le=3)

    # Optional offline speech-to-text fallback (requires faster-whisper).
    local_stt_enabled: bool = False
    local_stt_model: str = "base"

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
