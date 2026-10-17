"""داده نمونه آزمایشی — محتوای رسمی کتاب درسی نیست.

همه رکوردها با برچسب «محتوای نمونه آزمایشی» ثبت می‌شوند تا پیش از بازبینی و
تأیید متخصص، هیچ ادعایی درباره انطباق با کتاب درسی یا شماره صفحه مطرح نشود.
محل بارگذاری محتوای رسمی: پنل مدیریت محتوا + اسکریپت import در docs/CONTENT.md
ساختار فصل‌های ریاضی هشتم بر اساس فهرست شناخته‌شده کتاب است، اما متن آموزش و
سؤال‌ها نمونه‌های تألیف‌شده برای آزمون نرم‌افزار هستند.
"""
import json
from sqlalchemy.orm import Session
from . import models
from .security import hash_password

SAMPLE = "محتوای نمونه آزمایشی — نیازمند بازبینی و تأیید پیش از استفاده رسمی"


def _q(topic_id, text, correct, explanation, difficulty=1, qtype="mcq", options=None,
       hints=None, diagnostic=False):
    return models.Question(
        topic_id=topic_id, qtype=qtype, text=text,
        options_json=json.dumps(options or [], ensure_ascii=False),
        correct_answer=str(correct), explanation=explanation,
        hints_json=json.dumps(hints or [], ensure_ascii=False),
        difficulty=difficulty, is_diagnostic=diagnostic,
        source=SAMPLE, content_version="0.1-sample", review_status="draft")


def seed(db: Session):
    if db.query(models.Book).first():
        return {"already_seeded": True}

    # کاربران نمایشی (فقط برای محیط توسعه — در تولید حذف/تغییر شوند)
    admin = models.User(email="admin@example.com", full_name="مدیر محتوا",
                        hashed_password=hash_password("Admin1234"), role="admin")
    parent = models.User(email="parent@example.com", full_name="والد نمونه",
                         hashed_password=hash_password("Parent1234"), role="parent")
    student = models.User(email="student@example.com", full_name="دانش‌آموز نمونه",
                          hashed_password=hash_password("Student1234"), role="student")
    db.add_all([admin, parent, student])
    db.flush()
    db.add(models.ParentStudentLink(parent_id=parent.id, student_id=student.id))

    math = models.Book(grade=8, title="ریاضی هشتم (نمونه)", subject="ریاضی",
                       source_note=SAMPLE, content_version="0.1-sample", review_status="draft")
    farsi = models.Book(grade=8, title="فارسی هشتم (نمونه)", subject="فارسی",
                        source_note=SAMPLE, content_version="0.1-sample", review_status="draft")
    db.add_all([math, farsi])
    db.flush()

    # ---------- ریاضی: فصل ۱ عددهای صحیح و گویا ----------
    ch1 = models.Chapter(book_id=math.id, title="فصل ۱: عددهای صحیح و گویا", order=1)
    ch2 = models.Chapter(book_id=math.id, title="فصل ۲: عددهای اول", order=2)
    db.add_all([ch1, ch2])
    db.flush()

    t1 = models.Topic(chapter_id=ch1.id, title="جمع و تفریق عددهای صحیح", order=1)
    t2 = models.Topic(chapter_id=ch1.id, title="عددهای گویا و نمایش روی محور", order=2,
                      prerequisite_topic_ids="")
    t3 = models.Topic(chapter_id=ch2.id, title="عدد اول و مرکب", order=1)
    db.add_all([t1, t2, t3])
    db.flush()
    t2.prerequisite_topic_ids = str(t1.id)

    for tid, txt in [
        (t1.id, "جمع و تفریق عددهای صحیح با علامت‌های هم‌نام و ناهم‌نام را انجام دهد."),
        (t2.id, "عدد گویا را به صورت کسر بنویسد و روی محور نمایش دهد."),
        (t3.id, "عددهای اول را از مرکب تشخیص دهد."),
    ]:
        db.add(models.LearningObjective(topic_id=tid, text=txt))

    db.add_all([
        models.Lesson(topic_id=t1.id, title="جمع و تفریق عددهای صحیح",
                      steps_json=json.dumps([
                          "قدم ۱: علامت هر عدد را مشخص کن؛ عدد مثبت یعنی حرکت به راست و منفی یعنی حرکت به چپ روی محور.",
                          "قدم ۲: اگر علامت‌ها یکی بود، قدر مطلق‌ها را جمع کن و همان علامت را بگذار.",
                          "قدم ۳: اگر علامت‌ها متفاوت بود، قدر مطلق بزرگ‌تر منهای کوچک‌تر و علامتِ عدد بزرگ‌تر را بگذار.",
                      ], ensure_ascii=False),
                      example_text="مثال: ‎(-۷) + (+۳)‎ — علامت‌ها متفاوت‌اند؛ ‎۷-۳=۴‎ و علامت عدد بزرگ‌تر منفی است؛ پاسخ: ‎-۴‎",
                      simpler_text="عددهای منفی را مثل بدهی و مثبت را مثل دارایی ببین: ۷ واحد بدهی و ۳ واحد دارایی یعنی در مجموع ۴ واحد بدهی داری.",
                      source=SAMPLE),
        models.Lesson(topic_id=t2.id, title="عددهای گویا",
                      steps_json=json.dumps([
                          "قدم ۱: هر عددی که بتوان آن را به صورت کسر a/b با b≠۰ نوشت، گویاست.",
                          "قدم ۲: برای نمایش روی محور، بازه بین دو عدد صحیح را به قسمت‌های مساوی تقسیم کن.",
                      ], ensure_ascii=False),
                      example_text="مثال: ‎۳/۴‎ بین ۰ و ۱ قرار می‌گیرد؛ بازه را ۴ قسمت کن و ۳ قسمت جلو برو.",
                      simpler_text="عدد گویا یعنی عدد کسری؛ مثل نصف پیتزا یا سه‌چهارم لیوان آب.",
                      source=SAMPLE),
        models.Lesson(topic_id=t3.id, title="عدد اول و مرکب",
                      steps_json=json.dumps([
                          "قدم ۱: عدد اول فقط دو مقسوم‌علیه دارد: ۱ و خودش.",
                          "قدم ۲: عدد مرکب بیش از دو مقسوم‌علیه دارد. عدد ۱ نه اول است نه مرکب.",
                      ], ensure_ascii=False),
                      example_text="مثال: ۷ اول است (فقط ۱ و ۷)؛ ۹ مرکب است (۱ و ۳ و ۹).",
                      simpler_text="عدد اول مثل عددی است که فقط خودش و یک به آن بخش‌پذیرند.",
                      source=SAMPLE),
    ])

    questions = [
        _q(t1.id, "حاصل ‎(-۵) + (-۳)‎ کدام است؟", "-8", "هر دو منفی‌اند: ۵+۳=۸ با علامت منفی.", 1,
           options=["-8", "8", "-2", "2"], hints=["به علامت هر دو عدد نگاه کن.", "اگر هر دو منفی باشند، قدر مطلق‌ها جمع می‌شود."], diagnostic=True),
        _q(t1.id, "حاصل ‎(+۹) + (-۴)‎ کدام است؟", "5", "علامت‌ها متفاوت‌اند: ۹-۴=۵ و علامت مثبتِ عدد بزرگ‌تر.", 1,
           options=["13", "5", "-5", "-13"], hints=["علامت‌ها متفاوت‌اند.", "قدر مطلق بزرگ‌تر را منهای کوچک‌تر کن."], diagnostic=True),
        _q(t1.id, "حاصل ‎(-۶) - (-۲)‎ را به صورت عدد بنویس.", "-4", "تفریقِ عدد منفی یعنی جمع قرینه: ‎(-۶)+(+۲)=-۴‎", 2,
           qtype="numeric", hints=["منهایِ منفی، می‌شود مثبت.", "یعنی ‎-۶ + ۲‎ را حساب کن."], diagnostic=True),
        _q(t2.id, "کدام عدد گویا نیست؟", "√2", "√2 را نمی‌توان به صورت کسر دو عدد صحیح نوشت.", 2,
           options=["۳/۵", "-۷", "۰٫۲۵", "√2"], hints=["تعریف عدد گویا را به یاد بیاور: کسر a/b", "کدام گزینه کسری نیست؟"], diagnostic=True),
        _q(t2.id, "عدد ‎-۱/۲‎ روی محور بین کدام دو عدد صحیح قرار دارد؟", "بین ‎-۱ و ۰", "‎-۱/۲‎ یعنی نیم واحد سمت چپِ صفر.", 1,
           options=["بین ‎۰ و ۱", "بین ‎-۱ و ۰", "بین ‎-۲ و -۱", "دقیقاً روی ‎-۱"], diagnostic=True),
        _q(t3.id, "کدام عدد اول است؟", "۱۳", "۱۳ فقط بر ۱ و خودش بخش‌پذیر است.", 1,
           options=["۹", "۱۳", "۱۵", "۲۱"], hints=["مقسوم‌علیه‌های هر گزینه را بررسی کن.", "۹ بر ۳ بخش‌پذیر است."], diagnostic=True),
        _q(t3.id, "عدد ۱ اول است.", "نادرست", "عدد ۱ فقط یک مقسوم‌علیه دارد؛ پس نه اول است نه مرکب.", 1,
           qtype="truefalse", options=["درست", "نادرست"], diagnostic=True),
    ]
    db.add_all(questions)
    db.flush()
    diag = models.Quiz(title="آزمون تشخیصی آغازین (نمونه)", quiz_type="diagnostic",
                       question_ids=",".join(str(q.id) for q in questions))
    db.add(diag)

    # ---------- فارسی: روان‌خوانی و درک مطلب ----------
    fch1 = models.Chapter(book_id=farsi.id, title="فصل ۱: زیبایی آفرینش (نمونه)", order=1)
    db.add(fch1)
    db.flush()
    ft1 = models.Topic(chapter_id=fch1.id, title="روان‌خوانی و درک مطلب", order=1)
    db.add(ft1)
    db.flush()
    db.add(models.LearningObjective(topic_id=ft1.id,
                                    text="متن فارسی را روان، با مکث درست و با درک معنا بخواند."))
    reading = ("به نام خداوند جان و خرد، کزین برتر اندیشه برنگذرد. "
               "خداوند نام و خداوند جای، خداوند روزی‌ده رهنمای. "
               "این بیت‌ها آغاز شاهنامه فردوسی است؛ کتابی که داستان‌های کهن ایران را به شعر گفته است.")
    db.add(models.Lesson(topic_id=ft1.id, title="روان‌خوانی: آغاز شاهنامه",
                         steps_json=json.dumps([
                             "قدم ۱: اول متن را یک بار با چشم بخوان تا کلمه‌های سخت را پیدا کنی.",
                             "قدم ۲: متن را آهسته و با مکث در پایان هر مصراع بخوان.",
                             "قدم ۳: حالا با صدای بلند و رسا بخوان؛ سرعت کمتر و خواندن درست، بهتر از تندخوانیِ پراشتباه است.",
                         ], ensure_ascii=False),
                         example_text="نمونه خواندن: در پایان هر مصراع کمی مکث کن و کلمه «خداوند» را کشیده و روشن بخوان.",
                         simpler_text="اول آرام بخوان، بعد که راه افتادی کمی تندتر شو.",
                         reading_text=reading, source=SAMPLE))
    fq = _q(ft1.id, "شاهنامه اثر کدام شاعر است؟", "فردوسی", "در متن آمده است که این کتاب، شاهنامه فردوسی است.", 1,
            options=["فردوسی", "سعدی", "حافظ", "مولوی"], diagnostic=True)
    db.add(fq)
    db.flush()
    db.add(models.Quiz(title="آزمون تشخیصی فارسی (نمونه)", quiz_type="diagnostic",
                       question_ids=str(fq.id)))
    db.commit()
    return {"seeded": True, "demo_users": ["parent@example.com", "student@example.com", "admin@example.com"]}
