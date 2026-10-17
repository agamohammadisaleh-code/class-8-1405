"""تنظیمات سرور — همه مقادیر حساس فقط از متغیرهای محیطی خوانده می‌شوند."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "مربی هوشمند پایه هشتم"
    # در محیط واقعی حتماً SECRET_KEY را با یک مقدار تصادفی بلند جایگزین کنید.
    secret_key: str = "dev-only-change-me-in-production-0123456789"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # ۲۴ ساعت
    # پیش‌فرض توسعه: SQLite — در تولید: postgresql+psycopg2://user:pass@host/db
    database_url: str = "sqlite:///./tutor8.db"
    # اتصال اختیاری به مدل زبانی خارجی (فقط از سمت سرور). خالی = مربی قاعده‌محور آفلاین
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_model: str = ""
    cors_origins: str = "*"

    class Config:
        env_file = ".env"


settings = Settings()
