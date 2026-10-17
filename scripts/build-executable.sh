#!/usr/bin/env bash
# ساخت فایل اجرایی واحد «morabi-hoshmand» (وب + API در یک فایل)
#
# چرا خوداستخراج‌شونده و نه PyInstaller؟ در محیط ساخت فعلی، پایتون دبیان
# استاتیک است (libpython اشتراکی ندارد)، هدرهای توسعه و دسترسی شبکه apt و
# دانلود CPython مستقل هم مسدود است؛ PyInstaller عملاً ساخته نمی‌شود.
# این روش روی هر لینوکسی با python3>=3.10 کار می‌کند: در اولین اجرا،
# وابستگی‌ها و برنامه در ~/.cache/morabi-hoshmand/<md5> استخراج می‌شوند.
#
# خروجی: release/morabi-hoshmand
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "۱) ساخت رابط وب..."
(cd web && npm install --no-audit --no-fund && npm run build)

echo "۲) آماده‌سازی بسته برنامه و وابستگی‌ها..."
rm -rf build_payload server/web_dist
mkdir -p build_payload
cp -r web/dist server/web_dist
cp -r server/app build_payload/app
cp server/run.py build_payload/run.py
cp -r server/web_dist build_payload/web_dist
find build_payload -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

.venv/bin/pip install --quiet --target build_payload/deps \
  "fastapi==0.143.3" "uvicorn" "sqlalchemy>=2.0" "pydantic>=2.0" \
  "pydantic-settings" "python-jose[cryptography]" "bcrypt" \
  "python-multipart" "email-validator"

echo "۳) ساخت فایل اجرایی تک‌فایل..."
tar -czf build_payload.tar.gz -C build_payload .
BUILD_ID=$(md5sum build_payload.tar.gz | cut -d' ' -f1)
mkdir -p release
{
  cat <<HEADER
#!/bin/sh
# مربی هوشمند پایه هشتم — فایل اجرایی واحد (وب + سرور)
# اجرا: ./morabi-hoshmand   |   پورت دیگر: PORT=9000 ./morabi-hoshmand
# نیازمندی روی دستگاه مقصد: python3 نسخه 3.10 یا بالاتر
DIR="\$HOME/.cache/morabi-hoshmand/$BUILD_ID"
if [ ! -f "\$DIR/.ready" ]; then
  echo "نصب اولیه مربی هوشمند..." >&2
  mkdir -p "\$DIR"
  LINE=\$(awk '/^__MORABI_PAYLOAD__\$/{print NR+1; exit}' "\$0")
  tail -n +\$LINE "\$0" | tar xz -C "\$DIR" && touch "\$DIR/.ready"
fi
export PYTHONPATH="\$DIR/deps:\$DIR"
export AUTO_SEED="\${AUTO_SEED:-1}"
exec python3 "\$DIR/run.py" "\$@"
__MORABI_PAYLOAD__
HEADER
  cat build_payload.tar.gz
} > release/morabi-hoshmand
chmod +x release/morabi-hoshmand
rm -rf build_payload build_payload.tar.gz
ls -lh release/morabi-hoshmand
echo "تمام شد. اجرا: ./release/morabi-hoshmand  سپس http://localhost:8000"
