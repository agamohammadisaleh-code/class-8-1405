# راهنمای اجرا و استقرار

## اجرای سریع (توسعه)

```bash
python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
cd server && ../.venv/bin/python -c "
from app.database import Base, engine, SessionLocal
from app import models; Base.metadata.create_all(bind=engine)
from app.seed_data import seed; print(seed(SessionLocal()))"
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000   # از داخل server/
cd ../web && npm install && npm run dev    # http://localhost:5173
```

حساب‌های نمایشی: `student@example.com/Student1234`، `parent@example.com/Parent1234`،
`admin@example.com/Admin1234` — در محیط واقعی حتماً حذف یا تغییر داده شوند و
`SECRET_KEY` تصادفی تنظیم شود (`.env` از روی `server/.env.example`).

## استقرار با Docker Compose

```bash
SECRET_KEY=$(openssl rand -hex 32) POSTGRES_PASSWORD=... docker compose up --build
# وب: http://localhost:8080 — API: http://localhost:8000/docs
```

## آزمون‌ها

```bash
cd server && ../.venv/bin/python -m pytest tests/ -v
cd ../web && npm run build
```

## رفع خطای رایج

- «ابتدا وارد حساب شوید»: توکن منقضی شده؛ دوباره وارد شوید.
- خطای اتصال وب به API: سرور روی پورت ۸۰۰۰ در حال اجرا و پروکسی Vite فعال باشد.
- به‌روزرسانی: `git pull`، نصب وابستگی‌ها، اجرای مجدد سرور (جداول با SQLAlchemy ساخته/به‌روز می‌شوند؛
  برای تغییرات مخرب ستون‌ها از مهاجرت دستی SQL استفاده و قبلش پشتیبان بگیرید).
