"""مدل‌های پایگاه داده.

ساختار محتوا: پایه ← کتاب ← فصل ← موضوع ← هدف یادگیری ← آموزش ← تمرین ← آزمون ← مرور
هر درس و سؤال دارای منبع، نسخه محتوا، سطح دشواری، پاسخ صحیح، توضیح پاسخ و وضعیت بازبینی است.
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, ForeignKey, DateTime, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .database import Base


def now():
    return datetime.datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # parent | student | admin
    is_active = Column(Boolean, default=True)
    # رضایت والد برای ضبط صدای دانش‌آموز (فقط والد می‌تواند تغییر دهد)
    voice_recording_allowed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class ParentStudentLink(Base):
    __tablename__ = "parent_student_links"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)


# ---------- محتوا ----------
class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True)
    grade = Column(Integer, default=8)
    title = Column(String(255), nullable=False)
    subject = Column(String(100), nullable=False)
    source_note = Column(Text, default="")
    content_version = Column(String(50), default="0.1-sample")
    review_status = Column(String(20), default="draft")  # draft | approved
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    title = Column(String(255), nullable=False)
    order = Column(Integer, default=1)
    book = relationship("Book", back_populates="chapters")
    topics = relationship("Topic", back_populates="chapter", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    title = Column(String(255), nullable=False)
    order = Column(Integer, default=1)
    prerequisite_topic_ids = Column(String(255), default="")  # مثال: "1,2"
    chapter = relationship("Chapter", back_populates="topics")


class LearningObjective(Base):
    __tablename__ = "learning_objectives"
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    text = Column(Text, nullable=False)


class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    title = Column(String(255), nullable=False)
    steps_json = Column(Text, default="[]")        # آموزش مرحله‌به‌مرحله (JSON)
    example_text = Column(Text, default="")        # مثال حل‌شده
    simpler_text = Column(Text, default="")        # توضیح ساده‌تر
    reading_text = Column(Text, default="")        # متن روان‌خوانی (فارسی)
    source = Column(String(255), default="محتوای نمونه آزمایشی")
    content_version = Column(String(50), default="0.1-sample")
    review_status = Column(String(20), default="draft")
    difficulty = Column(Integer, default=1)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    qtype = Column(String(20), default="mcq")  # mcq | truefalse | numeric | short
    text = Column(Text, nullable=False)
    options_json = Column(Text, default="[]")
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, default="")
    hints_json = Column(Text, default="[]")  # راهنمایی تدریجی
    difficulty = Column(Integer, default=1)  # 1 آسان، 2 متوسط، 3 دشوار
    is_diagnostic = Column(Boolean, default=False)
    source = Column(String(255), default="محتوای نمونه آزمایشی")
    content_version = Column(String(50), default="0.1-sample")
    review_status = Column(String(20), default="draft")


# ---------- آزمون و پاسخ ----------
class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    quiz_type = Column(String(30), default="practice")  # diagnostic|practice|chapter|final|comprehensive|review
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    question_ids = Column(Text, default="")  # "1,2,3"


class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(String(20), default="independent")  # guided | independent
    status = Column(String(20), default="in_progress")  # in_progress | submitted
    score = Column(Float, nullable=True)
    total = Column(Integer, default=0)
    started_at = Column(DateTime, default=now)
    submitted_at = Column(DateTime, nullable=True)


class Answer(Base):
    __tablename__ = "answers"
    # شناسه یکتای سمت کاربر برای جلوگیری از ثبت تکراری هنگام همگام‌سازی آفلاین
    __table_args__ = (UniqueConstraint("client_id", name="uq_answer_client_id"),)
    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), nullable=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    given_answer = Column(Text, default="")
    is_correct = Column(Boolean, nullable=True)
    hints_used = Column(Integer, default=0)
    answered_offline = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class Mistake(Base):
    __tablename__ = "mistakes"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    # دسته‌بندی فقط بر اساس شواهد: concept|calculation|reading|unknown
    category = Column(String(30), default="unknown")
    count = Column(Integer, default=1)
    resolved = Column(Boolean, default=False)
    last_seen = Column(DateTime, default=now)


class ReviewSchedule(Base):
    """مرور فاصله‌دار (الگوریتم ساده شبیه SM-2)."""
    __tablename__ = "review_schedules"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    interval_days = Column(Float, default=1.0)
    ease = Column(Float, default=2.5)
    repetitions = Column(Integer, default=0)
    next_review_at = Column(DateTime, default=now)


class StudyTask(Base):
    __tablename__ = "study_tasks"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    due_date = Column(String(20), default="")  # YYYY-MM-DD
    status = Column(String(20), default="pending")  # pending | done
    parent_comment = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class StudyLog(Base):
    """ثبت تقریبی زمان فعالیت — معادل یادگیری واقعی نیست و در گزارش‌ها با همین برچسب نمایش داده می‌شود."""
    __tablename__ = "study_logs"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity = Column(String(100), default="practice")
    seconds = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)


class ReadingRecord(Base):
    __tablename__ = "reading_records"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    words_per_minute = Column(Float, nullable=True)
    duration_seconds = Column(Float, default=0)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class ParentComment(Base):
    __tablename__ = "parent_comments"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("study_tasks.id"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now)
