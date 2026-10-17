"""آزمون‌های پذیرش مربی هوشمند پایه هشتم.

پوشش: ورود/خروج، کنترل دسترسی نقش‌ها، محاسبه نمره، عدم افشای پاسخ در آزمون
مستقل، ثبت اشتباه، همگام‌سازی آفلاین بدون تکرار، مربی و مرور فاصله‌دار.
اجرا:  pytest -v
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_tutor8.db"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if os.path.exists("test_tutor8.db"):
    os.remove("test_tutor8.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.seed_data import seed  # noqa: E402

client = TestClient(app)
db = SessionLocal()
seed(db)
db.close()


def login(email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


PARENT = login("parent@example.com", "Parent1234")
STUDENT = login("student@example.com", "Student1234")


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_wrong_password():
    r = client.post("/api/auth/login", json={"email": "student@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_unauthenticated_rejected():
    assert client.get("/api/books").status_code == 401


def test_student_cannot_create_student():
    r = client.post("/api/parent/students", headers=STUDENT,
                    json={"email": "x@example.com", "full_name": "تست تست", "password": "Test1234"})
    assert r.status_code == 403


def test_student_cannot_see_parent_report():
    me = client.get("/api/auth/me", headers=PARENT).json()
    students = client.get("/api/parent/students", headers=PARENT).json()
    sid = students[0]["id"]
    r = client.get(f"/api/parent/students/{sid}/report", headers=STUDENT)
    assert r.status_code == 403


def test_student_cannot_access_other_student_progress():
    r = client.get("/api/progress?student_id=99999", headers=STUDENT)
    assert r.status_code == 403


def test_books_and_lesson_fa():
    books = client.get("/api/books", headers=STUDENT).json()
    assert len(books) == 2
    tree = client.get(f"/api/books/{books[0]['id']}/tree", headers=STUDENT).json()
    lesson_id = tree["chapters"][0]["topics"][0]["lesson_id"]
    lesson = client.get(f"/api/lessons/{lesson_id}", headers=STUDENT).json()
    assert lesson["steps"] and lesson["example"]
    simpler = client.get(f"/api/lessons/{lesson_id}?simpler=true", headers=STUDENT).json()
    assert len(simpler["steps"]) >= len(lesson["steps"])


def _diagnostic_quiz_id():
    quizzes = client.get("/api/quizzes", headers=STUDENT).json()
    return [q for q in quizzes if q["quiz_type"] == "diagnostic"][0]["id"]


def test_independent_quiz_hides_answers_and_grades_correctly():
    start = client.post("/api/attempts", headers=STUDENT,
                        json={"quiz_id": _diagnostic_quiz_id(), "mode": "independent"}).json()
    assert "correct_answer" not in start["questions"][0]
    aid = start["attempt_id"]
    # پاسخ به همه سؤال‌ها (عمداً از کلید داخلی تست استفاده می‌شود)
    from app.database import SessionLocal as SL
    from app import models
    s = SL()
    correct_count = 0
    for qd in start["questions"]:
        q = s.query(models.Question).get(qd["id"])
        r = client.post(f"/api/attempts/{aid}/answers", headers=STUDENT,
                        json={"question_id": q.id, "given_answer": q.correct_answer})
        assert r.json()["is_correct"] is None  # در حالت مستقل نباید فاش شود
        correct_count += 1
    s.close()
    res = client.post(f"/api/attempts/{aid}/submit", headers=STUDENT).json()
    assert res["score"] == 100.0 and res["correct"] == correct_count


def test_wrong_answers_create_mistakes_and_review():
    start = client.post("/api/attempts", headers=STUDENT,
                        json={"quiz_id": _diagnostic_quiz_id(), "mode": "guided"}).json()
    aid = start["attempt_id"]
    qid = start["questions"][0]["id"]
    r = client.post(f"/api/attempts/{aid}/answers", headers=STUDENT,
                    json={"question_id": qid, "given_answer": "پاسخ اشتباه"})
    assert r.json()["is_correct"] is False  # در حالت هدایت‌شده بازخورد فوری مجاز است
    assert client.get("/api/mistakes", headers=STUDENT).json()
    due = client.get("/api/reviews/due", headers=STUDENT)
    assert due.status_code == 200


def test_offline_sync_is_idempotent():
    payload = [{"client_id": "test-uuid-0001", "question_id": 1, "given_answer": "-8"}]
    r1 = client.post("/api/sync/answers", headers=STUDENT, json=payload).json()
    r2 = client.post("/api/sync/answers", headers=STUDENT, json=payload).json()
    assert r1["saved"] == 1 and r2["saved"] == 0 and r2["duplicates_ignored"] == 1


def test_tutor_recommendation_and_honest_fallback():
    nxt = client.get("/api/tutor/next", headers=STUDENT).json()
    assert "reason" in nxt
    ask = client.post("/api/tutor/ask", headers=STUDENT,
                      json={"question": "عدد اول چیست و چطور تشخیص بدهم؟"}).json()
    assert ask["confident"] is True
    unknown = client.post("/api/tutor/ask", headers=STUDENT,
                          json={"question": "zzzz qqqq xxxx نامرتبط"}).json()
    assert unknown["confident"] is False  # نباید حدس قطعی بزند


def test_hint_ladder():
    h = client.get("/api/tutor/hint/1?level=1", headers=STUDENT).json()
    assert h["hint"]


def test_parent_report_uses_real_data():
    students = client.get("/api/parent/students", headers=PARENT).json()
    rep = client.get(f"/api/parent/students/{students[0]['id']}/report?period=weekly",
                     headers=PARENT).json()
    assert rep["practice_answers"] >= 1 and rep["tasks_total"] >= 0
    assert "معادل یادگیری واقعی نیست" in rep["note"]


def test_task_flow_parent_to_student():
    students = client.get("/api/parent/students", headers=PARENT).json()
    t = client.post("/api/tasks", headers=PARENT,
                    json={"student_id": students[0]["id"], "title": "تمرین فصل ۱ ریاضی",
                          "due_date": "2026-10-20"}).json()
    mine = client.get("/api/tasks", headers=STUDENT).json()
    assert any(x["id"] == t["id"] for x in mine)
    assert client.post(f"/api/tasks/{t['id']}/done", headers=STUDENT).json()["status"] == "done"
    c = client.post(f"/api/tasks/{t['id']}/comment", headers=PARENT,
                    json={"student_id": students[0]["id"], "text": "آفرین، انجام شد"})
    assert c.status_code == 200


def test_download_bundle_for_offline():
    bundle = client.get("/api/content/download-bundle", headers=STUDENT).json()
    assert bundle["lessons"] and bundle["questions"]
