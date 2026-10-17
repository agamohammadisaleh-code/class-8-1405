# اپ اندروید دانش‌آموز (Flutter)

کد منبع Flutter در `lib/main.dart` قرار دارد: ورود، خانه و پیشنهاد مربی، فهرست کتاب‌ها،
ذخیره پاسخ آفلاین در SQLite (`offline_answers`) و همگام‌سازی با `POST /api/sync/answers`.

## ساخت APK (نیازمند Flutter SDK و Android SDK)

در محیط فعلی توسعه (سندباکس ابری) Flutter، Java و Android SDK نصب نیست و امکان نصب
آن‌ها هم وجود ندارد؛ بنابراین APK در این محیط تولید نشد. روی ماشین توسعه خود:

```bash
cd mobile
flutter pub get
flutter build apk --release --dart-define=API_BASE=https://نشانی-سرور-شما
# خروجی: build/app/outputs/flutter-apk/app-release.apk
```

تا زمان ساخت APK، نسخه وب (PWA) همین قابلیت‌ها را روی موبایل ارائه می‌کند و قابل
نصب روی صفحه اصلی گوشی است (`web/`).
