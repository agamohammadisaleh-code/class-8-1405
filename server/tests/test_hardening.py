"""آزمون‌های سخت‌گیری (بازبینی منتقدانه): امنیت سید، سقف نمره، بازخورد تمرین،
بازبینی محتوای مدیر، تغییر گذرواژه و بسته آفلاین شامل آزمون‌ها."""
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_tutor8.db")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def login(email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


STUDENT = login("student@example.com", "Student1234")
ADMIN = login("admin@example.com", "Admin1234")


def test_seed_requires_admin():
    assert client.post("/api/admin/seed").status_code in (401, 403)
    assert client.post("/api/admin/seed", headers=STUDENT).status_code == 403
    r = client.post("/api/admin/seed", headers=ADMIN)
    assert r.status_code == 200


def test_attempt_score_never_exceeds_100_and_answer_replaced():
    from app.database import SessionLocal
    from app import models
    quizzes = client.get("/api/quizzes", headers=STUDENT).json()
    qid = [q for q in quizzes if q["quiz_type"] == "diagnostic"][0]["id"]
    start = client.post("/api/attempts", headers=STUDENT,
                        json={"quiz_id": qid, "mode": "guided"}).json()
    aid = start["attempt_id"]
    first = start["questions"][0]
    # اول اشتباه، بعد اصلاح همان سؤال: نباید دو پاسخ شمرده شود
    client.post(f"/api/attempts/{aid}/answers", headers=STUDENT,
                json={"question_id": first["id"], "given_answer": "اشتباه"})
    s = SessionLocal()
    correct = s.query(models.Question).get(first["id"]).correct_answer
    s.close()
    client.post(f"/api/attempts/{aid}/answers", headers=STUDENT,
                json={"question_id": first["id"], "given_answer": correct})
    res = client.post(f"/api/attempts/{aid}/submit", headers=STUDENT).json()
    assert res["score"] <= 100.0
    assert sum(1 for d in res["detail"] if d["question"]) == 1


def test_answer_to_question_outside_quiz_rejected():
    quizzes = client.get("/api/quizzes", headers=STUDENT).json()
    diag = [q for q in quizzes if q["quiz_type"] == "diagnostic"]
    small = min(diag, key=lambda q: q["question_count"])
    start = client.post("/api/attempts", headers=STUDENT,
                        json={"quiz_id": small["id"], "mode": "independent"}).json()
    in_quiz = {q["id"] for q in start["questions"]}
    bundle = client.get("/api/content/download-bundle", headers=STUDENT).json()
    outside = [q for q in bundle["questions"] if q["id"] not in in_quiz]
    assert outside, "برای این آزمون به سؤال بیرونی نیاز است"
    r = client.post(f"/api/attempts/{start['attempt_id']}/answers", headers=STUDENT,
                    json={"question_id": outside[0]["id"], "given_answer": "x"})
    assert r.status_code == 400


def test_practice_answer_gives_feedback_and_records_mistake():
    practice = client.get("/api/topics/1/practice", headers=STUDENT).json()
    assert practice
    r = client.post("/api/practice/answer", headers=STUDENT,
                    json={"question_id": practice[0]["id"], "given_answer": "حتماً اشتباه"}).json()
    assert r["is_correct"] is False and r["explanation"]
    r2 = client.post("/api/practice/answer", headers=STUDENT,
                     json={"question_id": practice[0]["id"],
                      "given_answer": r["correct_answer"]}).json()
    assert r2["is_correct"] is True


def test_admin_content_review_flow():
    assert client.get("/api/admin/content/pending", headers=STUDENT).status_code == 403
    pending = client.get("/api/admin/content/pending", headers=ADMIN).json()
    assert pending["lessons"] or pending["questions"]
    if pending["lessons"]:
        lid = pending["lessons"][0]["id"]
        r = client.post(f"/api/admin/content/lesson/{lid}/approve", headers=ADMIN)
        assert r.json()["review_status"] == "approved"
        after = client.get("/api/admin/content/pending", headers=ADMIN).json()
        assert all(l["id"] != lid for l in after["lessons"])


def test_change_password_flow():
    email = "parent2@example.com"
    client.post("/api/auth/register",
                json={"email": email, "full_name": "والد دوم", "password": "Parent1234"})
    h = login(email, "Parent1234")
    bad = client.post("/api/auth/change-password", headers=h,
                      json={"current_password": "wrong", "new_password": "Newpass123"})
    assert bad.status_code == 400
    ok = client.post("/api/auth/change-password", headers=h,
                     json={"current_password": "Parent1234", "new_password": "Newpass123"})
    assert ok.status_code == 200
    login(email, "Newpass123")
    assert client.post("/api/auth/login",
                       json={"email": email, "password": "Parent1234"}).status_code == 401


def test_bundle_includes_quizzes_for_offline():
    bundle = client.get("/api/content/download-bundle", headers=STUDENT).json()
    assert bundle["quizzes"] and bundle["quizzes"][0]["question_ids"]
