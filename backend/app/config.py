"""Application configuration.

All runtime configuration is environment-driven (12-factor).  The frontend
NEVER talks to the database directly; every setting that matters lives here
and is documented in `.env.example`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (…/CMMS-BASPAR)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- Core -------------------------------------------------------------
    app_name: str = "BASPAR CMMS"
    environment: str = "development"  # development | staging | production
    secret_key: str = "change-me-in-production-please-0123456789abcdef"
    api_prefix: str = "/api"

    # --- Database ---------------------------------------------------------
    # SQLite by default (zero-config, file based, transactional).
    # For PostgreSQL set e.g.:
    #   DATABASE_URL=postgresql+psycopg://user:pass@host:5432/cmms
    database_url: str = f"sqlite:///{BASE_DIR / 'storage' / 'db' / 'cmms.db'}"

    # --- Storage ------------------------------------------------------------
    storage_root: Path = BASE_DIR / "storage"
    max_upload_mb: int = 50
    allowed_upload_extensions: str = (
        "jpg,jpeg,png,gif,webp,pdf,txt,csv,xlsx,xls,doc,docx,mp3,wav,m4a,mp4,zip"
    )

    # --- Auth ---------------------------------------------------------------
    access_token_ttl_minutes: int = 12 * 60  # 12h working day
    jwt_algorithm: str = "HS256"
    login_rate_limit: int = 10  # attempts per window
    login_rate_window_seconds: int = 300

    # --- Bootstrap ------------------------------------------------------------
    admin_username: str = "admin"
    admin_password: str = "Admin@12345"

    # --- Backup ---------------------------------------------------------------
    backup_dir: Path = BASE_DIR / "storage" / "backups"

    @property
    def upload_root(self) -> Path:
        return self.storage_root / "uploads"

    def ensure_dirs(self) -> None:
        for p in (
            self.storage_root,
            self.storage_root / "db",
            self.upload_root,
            self.backup_dir,
        ):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
