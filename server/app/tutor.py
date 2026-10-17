"""مربی قاعده‌محور فارسی — بدون وابستگی به اینترنت کار می‌کند.

چرخه مربی: ارزیابی اولیه ← شناسایی پیش‌نیاز ضعیف ← انتخاب درس متناسب ←
توضیح کوتاه ← مثال حل‌شده ← تمرین هدایت‌شده با راهنمایی تدریجی ← آزمون مستقل ←
ثبت نتیجه و دسته‌بندی اشتباه بر اساس شواهد ← تمرین جبرانی و زمان مرور بعدی.

اگر مدل زبانی خارجی در سمت سرور پیکربندی شده باشد (LLM_API_KEY)، پاسخ آزاد
می‌تواند از آن استفاده کند؛ در غیر این صورت پاسخ فقط از محتوای تأییدشده/موجود
بانک محتوا ساخته می‌شود و در نبود داده کافی، مربی صریحاً عدم اطمینان را اعلام می‌کند.
"""
import datetime
import json
from sqlalchemy.orm import Session
from . import models


def mastery_by_topic(db: Session, student_id: int):
    """امتیاز تسلط هر موضوع از روی پاسخ‌های واقعی ثبت‌شده."""
    rows = db.query(models.Answer).filter(models.Answer.student_id == student_id,
                                          models.Answer.is_correct.isnot(None)).all()
    stats = {}
    qmap = {q.id: q for q in db.query(models.Question).all()}
    for a in rows:
        q = qmap.get(a.question_id)
        if not q:
            continue
        s = stats.setdefault(q.topic_id, {"correct": 0, "total": 0})
        s["total"] += 1
        if a.is_correct:
            s["correct"] += 1
    for v in stats.values():
        v["mastery"] = round(v["correct"] / v["total"], 2) if v["total"] else 0
    return stats


def weak_prerequisites(db: Session, student_id: int):
    stats = mastery_by_topic(db, student_id)
    weak = []
    for topic in db.query(models.Topic).all():
        s = stats.get(topic.id)
        if s and s["total"] >= 2 and s["mastery"] < 0.6:
            weak.append({"topic_id": topic.id, "title": topic.title, "mastery": s["mastery"]})
    return weak


def recommend_next(db: Session, student_id: int):
    """انتخاب درس بعدی: اول پیش‌نیازهای ضعیف، بعد موضوع بدون تمرین، بعد کمترین تسلط."""
    stats = mastery_by_topic(db, student_id)
    topics = db.query(models.Topic).order_by(models.Topic.order).all()
    # ۱) موضوعی که پیش‌نیازش ضعیف است، اول خود پیش‌نیاز پیشنهاد می‌شود
    for t in topics:
        s = stats.get(t.id)
        if s and s["total"] >= 2 and s["mastery"] < 0.6:
            return {"topic_id": t.id, "title": t.title,
                    "reason": "در این موضوع هنوز به تسلط کافی نرسیده‌ای؛ تمرین جبرانی پیشنهاد می‌شود.",
                    "action": "remedial"}
    # ۲) موضوعی که هنوز تمرینی ندارد
    for t in topics:
        if t.id not in stats:
            return {"topic_id": t.id, "title": t.title,
                    "reason": "این موضوع هنوز شروع نشده است.", "action": "learn"}
    # ۳) کمترین تسلط
    if stats:
        worst = min(stats.items(), key=lambda kv: kv[1]["mastery"])
        t = db.query(models.Topic).get(worst[0])
        return {"topic_id": t.id, "title": t.title if t else "",
                "reason": "کمترین میزان تسلط فعلی مربوط به این موضوع است.", "action": "practice"}
    if topics:
        return {"topic_id": topics[0].id, "title": topics[0].title,
                "reason": "شروع یادگیری از اولین موضوع.", "action": "learn"}
    return None


def categorize_mistake(question, given_answer: str) -> str:
    """دسته‌بندی اشتباه فقط بر اساس شواهد موجود؛ در نبود شواهد کافی: unknown."""
    if question is None:
        return "unknown"
    if question.qtype == "numeric":
        # پاسخ عددیِ نزدیک به جواب درست می‌تواند نشانه خطای محاسباتی باشد، نه قطعی
        try:
            if abs(float(given_answer) - float(question.correct_answer)) <= 1:
                return "calculation"
        except (TypeError, ValueError):
            pass
        return "concept"
    if question.qtype in ("mcq", "truefalse"):
        return "concept"
    return "unknown"


def schedule_review(db: Session, student_id: int, topic_id: int, was_correct: bool):
    """مرور فاصله‌دار: پاسخ درست ← فاصله بیشتر؛ پاسخ نادرست ← مرور فردا."""
    row = (db.query(models.ReviewSchedule)
           .filter_by(student_id=student_id, topic_id=topic_id).first())
    if row is None:
        row = models.ReviewSchedule(student_id=student_id, topic_id=topic_id,
                                    interval_days=1.0, ease=2.5, repetitions=0)
        db.add(row)
    row.repetitions = row.repetitions or 0
    row.interval_days = row.interval_days or 1.0
    row.ease = row.ease or 2.5
    if was_correct:
        row.repetitions += 1
        row.interval_days = 1 if row.repetitions == 1 else min(row.interval_days * row.ease, 30)
    else:
        row.repetitions = 0
        row.interval_days = 1
    row.next_review_at = datetime.datetime.utcnow() + datetime.timedelta(days=row.interval_days)
    return row


def grade_answer(question, given: str) -> bool:
    """تصحیح خودکار سؤال‌های دارای پاسخ مشخص (عینی و عددی)."""
    given = (given or "").strip()
    correct = (question.correct_answer or "").strip()
    if question.qtype == "numeric":
        try:
            return abs(float(given) - float(correct)) < 1e-9
        except (TypeError, ValueError):
            return False
    # مقایسه متنی با نرمال‌سازی فاصله و حروف عربی/فارسی رایج
    def norm(s):
        return (s.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
                .replace(" ", "").strip().lower())
    return norm(given) == norm(correct)


def ask_tutor(db: Session, question_text: str):
    """پاسخ‌گویی فقط از روی محتوای موجود بانک محتوا (جست‌وجوی کلیدواژه).

    در نبود تطابق کافی، عدم اطمینان صریحاً اعلام می‌شود.
    """
    text = (question_text or "").strip()
    if not text:
        return {"answer": "سؤالت را بنویس تا کمکت کنم.", "confident": False, "source": None}
    words = [w for w in text.replace("؟", " ").split() if len(w) > 2]
    best, best_score = None, 0
    for lesson in db.query(models.Lesson).all():
        hay = (lesson.title + " " + lesson.example_text + " " + lesson.steps_json)
        score = sum(1 for w in words if w in hay)
        if score > best_score:
            best, best_score = lesson, score
    if best is None or best_score == 0:
        return {"answer": "در محتوای تأییدشده‌ای که الان در دسترسم هست، پاسخ مطمئنی برای این سؤال پیدا نکردم. "
                          "موضوع را دقیق‌تر بنویس یا از معلمت بپرس؛ حدس قطعی نمی‌زنم.",
                "confident": False, "source": None}
    steps = json.loads(best.steps_json or "[]")
    body = " ".join(steps[:3])
    example = (best.example_text or "").removeprefix("مثال:").strip()
    return {"answer": f"{body} مثال: {example}".strip(),
            "confident": True,
            "source": {"lesson_id": best.id, "title": best.title,
                       "content_version": best.content_version, "review_status": best.review_status}}
