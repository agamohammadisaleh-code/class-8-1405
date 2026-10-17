"""نقطه ورود نسخه اجرایی واحد (وب + API روی یک پورت).

اجرا:  ./morabi-hoshmand            (پورت پیش‌فرض ۸۰۰۰)
       PORT=9000 ./morabi-hoshmand
در اولین اجرا، داده نمونه آزمایشی به‌صورت خودکار ساخته می‌شود (AUTO_SEED=0 برای غیرفعال‌کردن).
پایگاه داده در فایل tutor8.db کنار محل اجرا ساخته می‌شود.
"""
import os

os.environ.setdefault("AUTO_SEED", "1")

# پایگاه داده در پوشه داده کاربر می‌ماند تا با اجرای دوباره از هر مسیری حفظ شود
if not os.environ.get("DATABASE_URL"):
    _data_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "morabi-hoshmand")
    os.makedirs(_data_dir, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_data_dir, 'tutor8.db')}"

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
