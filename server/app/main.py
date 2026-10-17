"""سرور مرکزی مربی هوشمند پایه هشتم — FastAPI (تک‌برنامه‌ای، بدون میکروسرویس).

اجرا:  uvicorn app.main:app --host 0.0.0.0 --port 8000
مستندات تعاملی: /docs
"""
import datetime
import json
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from . import models, tutor
from .config import settings
from .database import Base, engine, get_db, SessionLocal
from .security import hash_password, verify_password, create_access_token, decode_token
from .seed_data import seed

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, version="1.1.0")
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])


# ---------- احراز هویت و کنترل دسترسی ----------
def current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "ابتدا وارد حساب شوید.")
    payload = decode_token(authorization.split(" ", 1)[1])
    if not payload:
        raise HTTPException(401, "نشست نامعتبر یا منقضی شده است.")
    user = db.query(models.User).get(int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "کاربر یافت نشد.")
    return user


def require_role(*roles):
    def dep(user=Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "به این بخش دسترسی ندارید.")
        return user
    return dep


def assert_student_access(db: Session, user, student_id: int):
    """دانش‌آموز فقط به داده خودش و والد فقط به دانش‌آموز پیوندخورده دسترسی دارد."""
    if user.role == "student" and user.id != student_id:
        raise HTTPException(403, "به اطلاعات دانش‌آموز دیگر دسترسی ندارید.")
    if user.role == "parent":
        link = db.query(models.ParentStudentLink).filter_by(parent_id=user.id, student_id=student_id).first()
        if not link:
            raise HTTPException(403, "این دانش‌آموز به حساب شما پیوند نشده است.")
    if user.role not in ("student", "parent", "admin"):
        raise HTTPException(403, "دسترسی نامعتبر")


def public_user(u):
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
            "voice_recording_allowed": u.voice_recording_allowed}


# ---------- طرح‌های ورودی ----------
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class CreateStudentIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=72)


class AnswerIn(BaseModel):
    question_id: int
    given_answer: str = ""
    hints_used: int = 0
    client_id: Optional[str] = None
    answered_offline: bool = False


class StartAttemptIn(BaseModel):
    quiz_id: int
    mode: str = "independent"  # guided | independent


class SyncAnswerItem(BaseModel):
    client_id: str
    question_id: int
    given_answer: str = ""
    hints_used: int = 0


class TaskIn(BaseModel):
    student_id: int
    title: str = Field(min_length=2, max_length=255)
    topic_id: Optional[int] = None
    due_date: str = ""


class CommentIn(BaseModel):
    student_id: int
    text: str = Field(min_length=1, max_length=2000)
    task_id: Optional[int] = None


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class ReadingIn(BaseModel):
    lesson_id: int
    duration_seconds: float = 0
    words_per_minute: Optional[float] = None
    note: str = ""


class LogIn(BaseModel):
    activity: str = "practice"
    seconds: int = 0


# ---------- سلامت و بذر داده ----------
@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name,
            "llm_configured": bool(settings.llm_api_key)}


@app.post("/api/admin/seed")
def run_seed(admin=Depends(require_role("admin")), db: Session = Depends(get_db)):
    """سید داده نمونه فقط با حساب مدیر سامانه مجاز است."""
    return seed(db)


# ---------- حساب‌ها ----------
@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """ثبت‌نام عمومی فقط برای والد است؛ حساب دانش‌آموز را والد می‌سازد."""
    if db.query(models.User).filter_by(email=body.email).first():
        raise HTTPException(400, "این ایمیل قبلاً ثبت شده است.")
    user = models.User(email=body.email, full_name=body.full_name,
                       hashed_password=hash_password(body.password), role="parent")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_access_token(user.id, user.role), "user": public_user(user)}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "ایمیل یا گذرواژه نادرست است.")
    return {"token": create_access_token(user.id, user.role), "user": public_user(user)}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return public_user(user)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


@app.post("/api/auth/change-password")
def change_password(body: ChangePasswordIn, user=Depends(current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "گذرواژه فعلی نادرست است.")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@app.post("/api/parent/students")
def create_student(body: CreateStudentIn, parent=Depends(require_role("parent")),
                   db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=body.email).first():
        raise HTTPException(400, "این ایمیل قبلاً ثبت شده است.")
    student = models.User(email=body.email, full_name=body.full_name,
                          hashed_password=hash_password(body.password), role="student")
    db.add(student)
    db.flush()
    db.add(models.ParentStudentLink(parent_id=parent.id, student_id=student.id))
    db.commit()
    return public_user(student)


@app.get("/api/parent/students")
def my_students(parent=Depends(require_role("parent")), db: Session = Depends(get_db)):
    links = db.query(models.ParentStudentLink).filter_by(parent_id=parent.id).all()
    return [public_user(db.query(models.User).get(l.student_id)) for l in links]


@app.post("/api/parent/students/{student_id}/voice-consent")
def voice_consent(student_id: int, allowed: bool, parent=Depends(require_role("parent")),
                  db: Session = Depends(get_db)):
    assert_student_access(db, parent, student_id)
    student = db.query(models.User).get(student_id)
    student.voice_recording_allowed = allowed
    db.commit()
    return {"voice_recording_allowed": allowed}


# ---------- محتوا ----------
def book_dict(b):
    return {"id": b.id, "grade": b.grade, "title": b.title, "subject": b.subject,
            "source_note": b.source_note, "content_version": b.content_version,
            "review_status": b.review_status}


@app.get("/api/books")
def books(db: Session = Depends(get_db), user=Depends(current_user)):
    return [book_dict(b) for b in db.query(models.Book).all()]


@app.get("/api/books/{book_id}/tree")
def book_tree(book_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    book = db.query(models.Book).get(book_id)
    if not book:
        raise HTTPException(404, "کتاب یافت نشد.")
    out = book_dict(book)
    out["chapters"] = []
    for ch in sorted(book.chapters, key=lambda c: c.order):
        topics = []
        for t in sorted(ch.topics, key=lambda x: x.order):
            lesson = db.query(models.Lesson).filter_by(topic_id=t.id).first()
            topics.append({"id": t.id, "title": t.title,
                           "lesson_id": lesson.id if lesson else None})
        out["chapters"].append({"id": ch.id, "title": ch.title, "topics": topics})
    return out


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: int, simpler: bool = False, db: Session = Depends(get_db),
               user=Depends(current_user)):
    lesson = db.query(models.Lesson).get(lesson_id)
    if not lesson:
        raise HTTPException(404, "درس یافت نشد.")
    steps = json.loads(lesson.steps_json or "[]")
    if simpler and lesson.simpler_text:
        steps = [lesson.simpler_text] + steps
    return {"id": lesson.id, "topic_id": lesson.topic_id, "title": lesson.title,
            "steps": steps, "example": lesson.example_text,
            "reading_text": lesson.reading_text, "source": lesson.source,
            "content_version": lesson.content_version, "review_status": lesson.review_status}


@app.get("/api/content/download-bundle")
def download_bundle(db: Session = Depends(get_db), user=Depends(current_user)):
    """بسته آفلاین: درس‌ها + سؤال‌ها + کلید تصحیح برای تصحیح عینی روی دستگاه.

    توجه امنیتی: در آزمون مستقل، پاسخ در رابط کاربری تا پایان آزمون نمایش داده
    نمی‌شود، اما کلید روی دستگاه ذخیره می‌شود؛ کاربر فنی می‌تواند آن را ببیند.
    برای آزمون‌های رسمی پرمخاطره، تصحیح باید فقط سمت سرور انجام شود.
    """
    lessons = db.query(models.Lesson).all()
    questions = db.query(models.Question).all()
    return {
        "version": "0.1-sample",
        "lessons": [{"id": l.id, "topic_id": l.topic_id, "title": l.title,
                     "steps": json.loads(l.steps_json or "[]"), "example": l.example_text,
                     "reading_text": l.reading_text} for l in lessons],
        "questions": [{"id": q.id, "topic_id": q.topic_id, "qtype": q.qtype, "text": q.text,
                       "options": json.loads(q.options_json or "[]"),
                       "correct_answer": q.correct_answer, "explanation": q.explanation,
                       "hints": json.loads(q.hints_json or "[]"),
                       "difficulty": q.difficulty} for q in questions],
        "quizzes": [{"id": z.id, "title": z.title, "quiz_type": z.quiz_type,
                     "question_ids": [int(x) for x in z.question_ids.split(",") if x]}
                    for z in db.query(models.Quiz).all()],
    }


# ---------- آزمون و تمرین ----------
def question_public(q, reveal: bool):
    d = {"id": q.id, "topic_id": q.topic_id, "qtype": q.qtype, "text": q.text,
         "options": json.loads(q.options_json or "[]"), "difficulty": q.difficulty}
    if reveal:
        d["correct_answer"] = q.correct_answer
        d["explanation"] = q.explanation
        d["hints"] = json.loads(q.hints_json or "[]")
    return d


@app.get("/api/quizzes")
def quizzes(db: Session = Depends(get_db), user=Depends(current_user)):
    return [{"id": q.id, "title": q.title, "quiz_type": q.quiz_type,
             "question_count": len([x for x in q.question_ids.split(",") if x])}
            for q in db.query(models.Quiz).all()]


@app.get("/api/topics/{topic_id}/practice")
def topic_practice(topic_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """تمرین هدایت‌شده از آسان به دشوار؛ پاسخ درست نمایش داده نمی‌شود، راهنمایی تدریجی دارد."""
    qs = (db.query(models.Question).filter_by(topic_id=topic_id)
          .order_by(models.Question.difficulty).all())
    return [question_public(q, reveal=False) | {"hints": json.loads(q.hints_json or "[]")} for q in qs]


class PracticeAnswerIn(BaseModel):
    question_id: int
    given_answer: str = ""
    hints_used: int = 0
    client_id: Optional[str] = None


@app.post("/api/practice/answer")
def practice_answer(body: PracticeAnswerIn, student=Depends(require_role("student")),
                    db: Session = Depends(get_db)):
    """تمرین آموزشی هدایت‌شده: پس از ثبت تلاش دانش‌آموز، درستی و توضیح نمایش داده
    می‌شود (پیش از پاسخ‌دادن، پاسخ فاش نمی‌شود و راهنمایی پلکانی در دسترس است)."""
    q = db.query(models.Question).get(body.question_id)
    if not q:
        raise HTTPException(404, "سؤال یافت نشد.")
    ans, _ = _save_answer(db, student.id, q, body.given_answer, body.hints_used,
                          body.client_id, False, None)
    db.commit()
    return {"is_correct": bool(ans.is_correct), "correct_answer": q.correct_answer,
            "explanation": q.explanation}


@app.post("/api/attempts")
def start_attempt(body: StartAttemptIn, student=Depends(require_role("student")),
                  db: Session = Depends(get_db)):
    quiz = db.query(models.Quiz).get(body.quiz_id)
    if not quiz:
        raise HTTPException(404, "آزمون یافت نشد.")
    mode = body.mode if body.mode in ("guided", "independent") else "independent"
    attempt = models.Attempt(quiz_id=quiz.id, student_id=student.id, mode=mode,
                             total=len([x for x in quiz.question_ids.split(",") if x]))
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    qids = [int(x) for x in quiz.question_ids.split(",") if x]
    questions = [question_public(db.query(models.Question).get(i), reveal=False)
                 for i in qids if db.query(models.Question).get(i)]
    # در حالت هدایت‌شده راهنمایی‌ها از ابتدا در دسترس‌اند؛ در مستقل نه
    if mode == "guided":
        for qd, i in zip(questions, qids):
            q = db.query(models.Question).get(i)
            qd["hints"] = json.loads(q.hints_json or "[]")
    return {"attempt_id": attempt.id, "mode": mode, "questions": questions}


def _save_answer(db, student_id, question, given, hints_used, client_id, offline, attempt_id=None):
    if client_id:
        old = db.query(models.Answer).filter_by(client_id=client_id).first()
        if old:  # جلوگیری از ثبت تکراری هنگام همگام‌سازی مجدد
            return old, False
    if attempt_id is not None:
        # داخل یک آزمون، پاسخ دوم به همان سؤال جایگزین پاسخ قبلی می‌شود تا
        # نمره از ۱۰۰ بیشتر نشود و هر سؤال فقط یک بار شمرده شود.
        prev = (db.query(models.Answer)
                .filter_by(attempt_id=attempt_id, question_id=question.id).first())
        if prev is not None:
            prev.given_answer = given
            prev.is_correct = tutor.grade_answer(question, given)
            prev.hints_used = hints_used
            db.flush()
            tutor.schedule_review(db, student_id, question.topic_id, bool(prev.is_correct))
            return prev, False
    correct = tutor.grade_answer(question, given)
    ans = models.Answer(client_id=client_id, attempt_id=attempt_id, question_id=question.id,
                        student_id=student_id, given_answer=given, is_correct=correct,
                        hints_used=hints_used, answered_offline=offline)
    db.add(ans)
    db.flush()
    if not correct:
        m = (db.query(models.Mistake).filter_by(student_id=student_id, topic_id=question.topic_id,
                                                question_id=question.id).first())
        if m:
            m.count += 1
            m.last_seen = datetime.datetime.utcnow()
            m.resolved = False
        else:
            db.add(models.Mistake(student_id=student_id, topic_id=question.topic_id,
                                  question_id=question.id,
                                  category=tutor.categorize_mistake(question, given)))
    tutor.schedule_review(db, student_id, question.topic_id, correct)
    return ans, True


@app.post("/api/attempts/{attempt_id}/answers")
def submit_answer(attempt_id: int, body: AnswerIn, student=Depends(require_role("student")),
                  db: Session = Depends(get_db)):
    attempt = db.query(models.Attempt).get(attempt_id)
    if not attempt or attempt.student_id != student.id:
        raise HTTPException(404, "تلاش آزمون یافت نشد.")
    if attempt.status == "submitted":
        raise HTTPException(400, "این آزمون قبلاً پایان یافته است.")
    q = db.query(models.Question).get(body.question_id)
    if not q:
        raise HTTPException(404, "سؤال یافت نشد.")
    quiz = db.query(models.Quiz).get(attempt.quiz_id)
    allowed = {int(x) for x in (quiz.question_ids or "").split(",") if x} if quiz else set()
    if q.id not in allowed:
        raise HTTPException(400, "این سؤال جزو این آزمون نیست.")
    ans, created = _save_answer(db, student.id, q, body.given_answer, body.hints_used,
                                body.client_id, body.answered_offline, attempt_id)
    db.commit()
    # در آزمون مستقل، پاسخ و توضیح فقط بعد از پایان آزمون آشکار می‌شود
    reveal = attempt.mode == "guided"
    return {"is_correct": ans.is_correct if reveal else None,
            "correct_answer": q.correct_answer if reveal else None,
            "explanation": q.explanation if reveal else None,
            "saved": created}


@app.post("/api/attempts/{attempt_id}/submit")
def finish_attempt(attempt_id: int, student=Depends(require_role("student")),
                   db: Session = Depends(get_db)):
    attempt = db.query(models.Attempt).get(attempt_id)
    if not attempt or attempt.student_id != student.id:
        raise HTTPException(404, "تلاش آزمون یافت نشد.")
    answers = db.query(models.Answer).filter_by(attempt_id=attempt_id).all()
    correct = sum(1 for a in answers if a.is_correct)
    attempt.score = round(100 * correct / attempt.total, 1) if attempt.total else 0
    attempt.status = "submitted"
    attempt.submitted_at = datetime.datetime.utcnow()
    db.commit()
    detail = []
    for a in answers:
        q = db.query(models.Question).get(a.question_id)
        detail.append({"question": q.text if q else "", "given": a.given_answer,
                       "is_correct": a.is_correct,
                       "correct_answer": q.correct_answer if q else "",
                       "explanation": q.explanation if q else ""})
    return {"attempt_id": attempt.id, "score": attempt.score, "correct": correct,
            "total": attempt.total, "mode": attempt.mode, "detail": detail}


@app.post("/api/sync/answers")
def sync_answers(items: List[SyncAnswerItem], student=Depends(require_role("student")),
                 db: Session = Depends(get_db)):
    """همگام‌سازی پاسخ‌های آفلاین؛ client_id یکتا از ثبت تکراری جلوگیری می‌کند."""
    saved, duplicates = 0, 0
    for it in items:
        q = db.query(models.Question).get(it.question_id)
        if not q:
            continue
        _, created = _save_answer(db, student.id, q, it.given_answer, it.hints_used,
                                  it.client_id, True)
        saved += 1 if created else 0
        duplicates += 0 if created else 1
    db.commit()
    return {"saved": saved, "duplicates_ignored": duplicates}


# ---------- مربی ----------
@app.get("/api/tutor/next")
def tutor_next(student=Depends(require_role("student")), db: Session = Depends(get_db)):
    return tutor.recommend_next(db, student.id) or {"reason": "هنوز محتوایی ثبت نشده است."}


@app.get("/api/tutor/weak-prerequisites")
def weak(student=Depends(require_role("student")), db: Session = Depends(get_db)):
    return tutor.weak_prerequisites(db, student.id)


@app.post("/api/tutor/ask")
def tutor_ask(body: AskIn, user=Depends(current_user), db: Session = Depends(get_db)):
    return tutor.ask_tutor(db, body.question)


@app.get("/api/tutor/hint/{question_id}")
def tutor_hint(question_id: int, level: int = 1, user=Depends(current_user),
               db: Session = Depends(get_db)):
    q = db.query(models.Question).get(question_id)
    if not q:
        raise HTTPException(404, "سؤال یافت نشد.")
    hints = json.loads(q.hints_json or "[]")
    if not hints:
        return {"hint": "برای این سؤال راهنمایی ثبت نشده است؛ اول درس را دوباره بخوان.", "level": level}
    idx = min(max(level, 1), len(hints)) - 1
    return {"hint": hints[idx], "level": idx + 1, "total_hints": len(hints)}


# ---------- پیشرفت، اشتباهات، مرور ----------
@app.get("/api/progress")
def progress(student_id: Optional[int] = None, user=Depends(current_user),
             db: Session = Depends(get_db)):
    sid = student_id or user.id
    assert_student_access(db, user, sid)
    stats = tutor.mastery_by_topic(db, sid)
    topics = {t.id: t.title for t in db.query(models.Topic).all()}
    mastered = [{"topic_id": i, "title": topics.get(i, ""), "mastery": s["mastery"]}
                for i, s in stats.items() if s["mastery"] >= 0.8]
    need_practice = [{"topic_id": i, "title": topics.get(i, ""), "mastery": s["mastery"]}
                     for i, s in stats.items() if s["mastery"] < 0.8]
    attempts = (db.query(models.Attempt).filter_by(student_id=sid, status="submitted")
                .order_by(models.Attempt.submitted_at.desc()).limit(20).all())
    return {"mastered": mastered, "need_practice": need_practice,
            "attempts": [{"id": a.id, "score": a.score, "mode": a.mode,
                          "submitted_at": str(a.submitted_at)} for a in attempts]}


@app.get("/api/mistakes")
def mistakes(student_id: Optional[int] = None, user=Depends(current_user),
             db: Session = Depends(get_db)):
    sid = student_id or user.id
    assert_student_access(db, user, sid)
    topics = {t.id: t.title for t in db.query(models.Topic).all()}
    rows = (db.query(models.Mistake).filter_by(student_id=sid, resolved=False)
            .order_by(models.Mistake.count.desc()).all())
    return [{"id": m.id, "topic_title": topics.get(m.topic_id, ""), "category": m.category,
             "count": m.count} for m in rows]


@app.get("/api/reviews/due")
def reviews_due(student=Depends(require_role("student")), db: Session = Depends(get_db)):
    rows = (db.query(models.ReviewSchedule)
            .filter(models.ReviewSchedule.student_id == student.id,
                    models.ReviewSchedule.next_review_at <= datetime.datetime.utcnow()).all())
    topics = {t.id: t.title for t in db.query(models.Topic).all()}
    return [{"topic_id": r.topic_id, "title": topics.get(r.topic_id, ""),
             "interval_days": r.interval_days} for r in rows]


# ---------- تکالیف و برنامه مطالعه ----------
@app.get("/api/tasks")
def list_tasks(student_id: Optional[int] = None, user=Depends(current_user),
               db: Session = Depends(get_db)):
    sid = student_id or user.id
    assert_student_access(db, user, sid)
    rows = db.query(models.StudyTask).filter_by(student_id=sid).order_by(models.StudyTask.id.desc()).all()
    return [{"id": t.id, "title": t.title, "topic_id": t.topic_id, "due_date": t.due_date,
             "status": t.status, "parent_comment": t.parent_comment} for t in rows]


@app.post("/api/tasks")
def create_task(body: TaskIn, user=Depends(current_user), db: Session = Depends(get_db)):
    assert_student_access(db, user, body.student_id)
    task = models.StudyTask(student_id=body.student_id, assigned_by=user.id,
                            title=body.title, topic_id=body.topic_id, due_date=body.due_date)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": task.id, "title": task.title, "status": task.status}


@app.post("/api/tasks/{task_id}/done")
def done_task(task_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    task = db.query(models.StudyTask).get(task_id)
    if not task:
        raise HTTPException(404, "تکلیف یافت نشد.")
    assert_student_access(db, user, task.student_id)
    task.status = "done"
    db.commit()
    return {"status": "done"}


@app.post("/api/tasks/{task_id}/comment")
def task_comment(task_id: int, body: CommentIn, parent=Depends(require_role("parent")),
                 db: Session = Depends(get_db)):
    task = db.query(models.StudyTask).get(task_id)
    if not task:
        raise HTTPException(404, "تکلیف یافت نشد.")
    assert_student_access(db, parent, task.student_id)
    task.parent_comment = body.text
    db.add(models.ParentComment(parent_id=parent.id, student_id=task.student_id,
                                 task_id=task_id, text=body.text))
    db.commit()
    return {"ok": True}


# ---------- گزارش والد (فقط از داده‌های واقعی ثبت‌شده) ----------
@app.get("/api/parent/students/{student_id}/report")
def parent_report(student_id: int, period: str = "weekly",
                  parent=Depends(require_role("parent")), db: Session = Depends(get_db)):
    assert_student_access(db, parent, student_id)
    days = 1 if period == "daily" else 7
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    attempts = (db.query(models.Attempt)
                .filter(models.Attempt.student_id == student_id,
                        models.Attempt.status == "submitted",
                        models.Attempt.submitted_at >= since).all())
    answers = (db.query(models.Answer)
               .filter(models.Answer.student_id == student_id,
                       models.Answer.created_at >= since).all())
    logs = (db.query(models.StudyLog)
            .filter(models.StudyLog.student_id == student_id,
                    models.StudyLog.created_at >= since).all())
    tasks = db.query(models.StudyTask).filter_by(student_id=student_id).all()
    topics = {t.id: t.title for t in db.query(models.Topic).all()}
    mistakes = (db.query(models.Mistake).filter_by(student_id=student_id, resolved=False)
                .order_by(models.Mistake.count.desc()).limit(5).all())
    return {
        "period": period,
        "note": "زمان فعالیت، تقریبی و بر اساس ثبت فعالیت در برنامه است و معادل یادگیری واقعی نیست.",
        "approx_study_minutes": round(sum(l.seconds for l in logs) / 60, 1),
        "practice_answers": len(answers),
        "quiz_scores": [{"score": a.score, "mode": a.mode, "when": str(a.submitted_at)} for a in attempts],
        "avg_score": round(sum(a.score or 0 for a in attempts) / len(attempts), 1) if attempts else None,
        "tasks_done": sum(1 for t in tasks if t.status == "done"),
        "tasks_total": len(tasks),
        "frequent_mistakes": [{"topic": topics.get(m.topic_id, ""), "count": m.count} for m in mistakes],
        "mastery": tutor.mastery_by_topic(db, student_id),
    }


@app.post("/api/study-log")
def study_log(body: LogIn, student=Depends(require_role("student")), db: Session = Depends(get_db)):
    db.add(models.StudyLog(student_id=student.id, activity=body.activity,
                           seconds=max(0, min(body.seconds, 3600))))
    db.commit()
    return {"ok": True}


# ---------- مدیریت محتوا (بازبینی و تأیید مدیر) ----------
@app.get("/api/admin/content/pending")
def pending_content(admin=Depends(require_role("admin")), db: Session = Depends(get_db)):
    lessons = db.query(models.Lesson).filter(models.Lesson.review_status != "approved").all()
    questions = db.query(models.Question).filter(models.Question.review_status != "approved").all()
    return {
        "lessons": [{"id": l.id, "title": l.title, "source": l.source,
                     "content_version": l.content_version} for l in lessons],
        "questions": [{"id": q.id, "text": q.text, "source": q.source,
                       "content_version": q.content_version} for q in questions],
    }


@app.post("/api/admin/content/{kind}/{item_id}/approve")
def approve_content(kind: str, item_id: int, admin=Depends(require_role("admin")),
                    db: Session = Depends(get_db)):
    model = {"lesson": models.Lesson, "question": models.Question}.get(kind)
    if model is None:
        raise HTTPException(400, "نوع محتوا نامعتبر است.")
    item = db.query(model).get(item_id)
    if not item:
        raise HTTPException(404, "محتوا یافت نشد.")
    item.review_status = "approved"
    db.commit()
    return {"ok": True, "review_status": "approved"}


@app.on_event("startup")
def _auto_seed():
    if settings.auto_seed:
        db = SessionLocal()
        try:
            if not db.query(models.Book).first():
                seed(db)
        finally:
            db.close()


# ---------- سرو یکپارچه رابط وب (نسخه اجرایی واحد) ----------
def _web_dist():
    import os
    import sys
    candidates = [settings.web_dist, os.path.join(os.getcwd(), "web_dist"),
                  os.path.join(os.path.dirname(__file__), "..", "web_dist")]
    if getattr(sys, "frozen", False):
        candidates.insert(0, os.path.join(sys._MEIPASS, "web_dist"))  # type: ignore[attr-defined]
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "index.html")):
            return c
    return None


_dist = _web_dist()
if _dist:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        import os
        if full_path.startswith("api/"):
            raise HTTPException(404, "مسیر یافت نشد.")
        target = os.path.join(_dist, full_path)
        if full_path and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(_dist, "index.html"))


@app.post("/api/reading/records")
def reading_record(body: ReadingIn, student=Depends(require_role("student")),
                   db: Session = Depends(get_db)):
    if not student.voice_recording_allowed:
        # ضبط صدا فقط با رضایت والد؛ ثبت سرعت خواندن بدون ضبط هم ممکن است
        body.note = (body.note + " | بدون ضبط صدا (رضایت والد ثبت نشده است)").strip()
    rec = models.ReadingRecord(student_id=student.id, lesson_id=body.lesson_id,
                               words_per_minute=body.words_per_minute,
                               duration_seconds=body.duration_seconds, note=body.note)
    db.add(rec)
    db.commit()
    return {"id": rec.id, "voice_recording_allowed": student.voice_recording_allowed}
