"""Settings, read once from environment variables and the .env file in the project root."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _jwt_secret(storage: Path) -> str:
    """Use JWT_SECRET if set; otherwise create one once and keep it, so logins survive restarts."""
    if os.getenv("JWT_SECRET"):
        return os.environ["JWT_SECRET"]
    path = storage / ".jwt_secret"
    if path.exists():
        return path.read_text().strip()
    storage.mkdir(parents=True, exist_ok=True)
    s = secrets.token_urlsafe(48)
    path.write_text(s)
    return s


def _apple_key() -> str | None:
    """APPLE_PRIVATE_KEY (the key text) or APPLE_PRIVATE_KEY_PATH (path to the .p8 file)."""
    if os.getenv("APPLE_PRIVATE_KEY"):
        return os.environ["APPLE_PRIVATE_KEY"].replace("\\n", "\n")
    path = os.getenv("APPLE_PRIVATE_KEY_PATH")
    return Path(path).read_text() if path and Path(path).exists() else None


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    platform_db_url: str
    tenant_db_url: str               # {id} is replaced by the business id
    demo_data_dir: Path
    jwt_secret: str
    jwt_hours: int
    groq_api_key: str | None
    groq_model: str
    hindsight_url: str
    hindsight_api_key: str | None
    demo_bank_id: str
    seed_demo: bool
    demo_email: str
    demo_password: str
    app_url: str = "http://localhost:5173"   # where the browser opens the app (used for sign-in redirects)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    apple_client_id: str | None = None        # the Services ID, e.g. app.cashwise.web
    apple_team_id: str | None = None
    apple_key_id: str | None = None
    apple_private_key: str | None = None      # contents of the .p8 key file
    cors_origins: list[str] = field(default_factory=list)
    # email (for sending reports); any SMTP server works, e.g. Gmail with an app password
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_ssl: bool = False               # True for port 465; otherwise STARTTLS is used
    run_scheduler: bool = True           # generate scheduled reports in the background
    report_tz: str = "Asia/Kolkata"      # scheduled reports run at this local time

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and (self.smtp_from or self.smtp_user))

    @property
    def hindsight_configured(self) -> bool:
        return bool(self.hindsight_api_key) or "localhost" in self.hindsight_url

    @staticmethod
    def from_env() -> "Settings":
        storage = Path(os.getenv("CASHWISE_STORAGE", ROOT / "storage")).resolve()
        (storage / "businesses").mkdir(parents=True, exist_ok=True)
        return Settings(
            storage_dir=storage,
            platform_db_url=os.getenv("PLATFORM_DB_URL", f"sqlite:///{storage / 'platform.db'}"),
            tenant_db_url=os.getenv("TENANT_DB_URL", f"sqlite:///{storage / 'businesses'}/{{id}}.db"),
            demo_data_dir=Path(os.getenv("DEMO_DATA_DIR", ROOT / "data")),
            jwt_secret=_jwt_secret(storage),
            jwt_hours=int(os.getenv("JWT_HOURS", "72")),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            hindsight_url=os.getenv("HINDSIGHT_URL", "https://api.hindsight.vectorize.io"),
            hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
            demo_bank_id=os.getenv("HINDSIGHT_BANK_ID", "malabar-electronics"),
            seed_demo=_bool("SEED_DEMO", True),
            demo_email=os.getenv("DEMO_EMAIL", "demo@cashwise.app"),
            demo_password=os.getenv("DEMO_PASSWORD", "demo1234"),
            # on Render, RENDER_EXTERNAL_URL is set for us (https://<name>.onrender.com)
            app_url=(os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:5173").rstrip("/"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID") or None,
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET") or None,
            github_client_id=os.getenv("GITHUB_CLIENT_ID") or None,
            github_client_secret=os.getenv("GITHUB_CLIENT_SECRET") or None,
            apple_client_id=os.getenv("APPLE_CLIENT_ID") or None,
            apple_team_id=os.getenv("APPLE_TEAM_ID") or None,
            apple_key_id=os.getenv("APPLE_KEY_ID") or None,
            apple_private_key=_apple_key(),
            smtp_host=os.getenv("SMTP_HOST") or None,
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER") or None,
            smtp_password=os.getenv("SMTP_PASSWORD") or None,
            smtp_from=os.getenv("SMTP_FROM") or None,
            smtp_ssl=_bool("SMTP_SSL", False),
            run_scheduler=_bool("RUN_SCHEDULER", True),
            report_tz=os.getenv("REPORT_TZ", "Asia/Kolkata"),
            cors_origins=[o.strip() for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()],
        )


settings = Settings.from_env()
