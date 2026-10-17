# مربی هوشمند آموزشی پایه هشتم 🎓

سامانه فارسی و راست‌چین آموزش، تمرین، آزمون و پیگیری پیشرفت دانش‌آموز پایه هشتم ایران،
برای یک دانش‌آموز و یک والد (با معماری آماده برای کاربران بیشتر).

> **وضعیت محتوا:** محتوای درسی فعلی **نمونه آزمایشی تألیف‌شده برای آزمون نرم‌افزار** است
> (ریاضی و فارسی هشتم) و روی همه رکوردها برچسب «نیازمند بازبینی» دارد. هیچ ادعایی درباره
> شماره صفحه یا متن رسمی کتاب مطرح نشده است. منبع رسمی کتاب‌ها: https://chap.sch.ir
> مسیر ورود و تأیید محتوای رسمی: [docs/CONTENT.md](docs/CONTENT.md)

## اجزا

| جزء | فناوری | مسیر |
|---|---|---|
| سرور API و مربی قاعده‌محور | Python + FastAPI + SQLAlchemy | `server/` |
| پنل وب والد + وب‌اپ دانش‌آموز (PWA آفلاین) | React + TypeScript + Vite | `web/` |
| اپ اندروید | Flutter + SQLite | `mobile/` |
| استقرار | Docker Compose (PostgreSQL + سرور + وب) | `docker-compose.yml` |

## اجرای سریع

```bash
python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
cd server
../.venv/bin/python -c "
from app.database import Base, engine, SessionLocal
from app import models; Base.metadata.create_all(bind=engine)
from app.seed_data import seed; print(seed(SessionLocal()))"
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
# ترمینال دوم:
cd web && npm install && npm run dev   # http://localhost:5173
```

حساب‌های نمایشی (فقط توسعه): دانش‌آموز `student@example.com / Student1234` —
والد `parent@example.com / Parent1234` — مدیر `admin@example.com / Admin1234`

## امکانات پیاده‌سازی‌شده

- دانش‌آموز: درس‌های مرحله‌به‌مرحله با مثال و توضیح ساده‌تر، آزمون تشخیصی، تمرین هدایت‌شده
  با راهنمایی پلکانی (بدون نمایش فوری پاسخ)، آزمون مستقل (بدون افشای پاسخ تا پایان)،
  تصحیح خودکار و توضیح پاسخ، دفتر اشتباهات، تکالیف و برنامه مطالعه، مرور فاصله‌دار،
  پیشنهاد بعدی مربی بر اساس نقاط ضعف، روان‌خوانی با صوت نمونه و ضبط اختیاری صدا.
- والد: گزارش روزانه/هفتگی فقط از داده واقعی (با برچسب «زمان تقریبی، نه معادل یادگیری»)،
  نمره‌ها با تفکیک «با کمک مربی/مستقل»، اشتباهات پرتکرار، تعیین تکلیف، ثبت نظر روی تکلیف،
  رضایت ضبط صدا، ساخت حساب دانش‌آموز.
- آفلاین: بسته دانلودی درس/تمرین، تصحیح عینی روی دستگاه، صف پاسخ با شناسه یکتا و
  همگام‌سازی بدون ثبت تکراری. مربی و تحلیل گفتار آفلاین نیستند و این در برنامه صریح نوشته شده است.
- امنیت: bcrypt + JWT، کنترل نقش و مالکیت داده در سرور، هیچ کلیدی در وب/اپ.

## فایل اجرایی آماده (نسخه ۱٫۱)

```bash
./release/morabi-hoshmand        # سپس http://localhost:8000
PORT=9000 ./release/morabi-hoshmand
```

یک فایل واحد (۲۱ مگابایت) شامل سرور و رابط وب؛ در اولین اجرا خودش را نصب و داده نمونه را
می‌سازد و داده کاربر در `~/.local/share/morabi-hoshmand/tutor8.db` می‌ماند.
روی دستگاه مقصد فقط `python3` نسخه ۳٫۱۰+ لازم است. بازسازی: `scripts/build-executable.sh`
(دلیل انتخاب این روش به جای PyInstaller و وضعیت APK در [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

## نتیجه آزمون‌ها (اجرای واقعی)

```
server: 22 passed (pytest: ۱۵ پذیرش + ۷ سخت‌گیری امنیتی/نمره‌دهی)
web:    npm run build موفق (TypeScript + Vite)
فایل اجرایی: از HOME خالی اجرا شد؛ ورود، کتاب، بازخورد تمرین، گزارش والد و
ماندگاری داده پس از راه‌اندازی مجدد روی همان فایل بررسی شد.
```

جزئیات پوشش پذیرش: [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) — معماری: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## محدودیت‌های صادقانه

- **APK ساخته نشد:** در این محیط Flutter/Java/Android SDK وجود ندارد. کد Flutter آماده است
  (`mobile/README.md`) و وب‌اپ PWA روی گوشی قابل نصب و استفاده است.
- Docker در این محیط نبود؛ سرور با SQLite واقعاً اجرا و آزموده شد و Compose برای سرور مقصد آماده است.
- مربی فعلی قاعده‌محور است (بدون نیاز به اینترنت/کلید)؛ اتصال LLM فقط از سمت سرور و اختیاری است.

فهرست کامل: [docs/LIMITATIONS.md](docs/LIMITATIONS.md) — حریم خصوصی و پشتیبان‌گیری: [docs/PRIVACY.md](docs/PRIVACY.md) — استقرار: [docs/DEPLOY.md](docs/DEPLOY.md)
