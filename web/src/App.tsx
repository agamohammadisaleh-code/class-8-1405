import { useCallback, useEffect, useRef, useState } from 'react';
import { api, getToken, setToken, queueAnswer, syncQueue, downloadBundle, loadBundle, loadQueue, uid } from './api';
import type { User } from './api';

const faNum = (n: unknown) => String(n ?? '—').replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[+d]);

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [err, setErr] = useState('');
  const [offlineMode, setOfflineMode] = useState(false);
  const [queueLen, setQueueLen] = useState(loadQueue().length);

  useEffect(() => {
    if (getToken()) api<User>('/api/auth/me').then(setUser).catch(() => setToken(null));
  }, []);

  const logout = () => { setToken(null); setUser(null); };

  const doSync = async () => {
    try {
      const r = await syncQueue();
      setQueueLen(0);
      alert(r ? `همگام‌سازی انجام شد: ${faNum(r.saved)} پاسخ ثبت شد.` : 'پاسخِ در انتظاری نیست.');
    } catch { alert('همگام‌سازی ناموفق بود؛ پاسخ‌ها روی دستگاه باقی ماندند.'); }
  };

  if (!user) return <AuthScreen onLogin={setUser} />;

  return (
    <div>
      <header className="top">
        <b>🎓 مربی هوشمند پایه هشتم</b>
        <span>
          {user.full_name} ({user.role === 'parent' ? 'والد' : user.role === 'student' ? 'دانش‌آموز' : 'مدیر'})
          <button className="ghost" style={{ marginInlineStart: 10 }} onClick={logout}>خروج</button>
        </span>
      </header>
      <main>
        <div className="card" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <label>
            <input type="checkbox" style={{ width: 'auto' }} checked={offlineMode}
              onChange={(e) => setOfflineMode(e.target.checked)} /> شبیه‌سازی حالت آفلاین (تمرین بدون اینترنت)
          </label>
          <button className="ghost" onClick={async () => { await downloadBundle(); alert('بسته درس و تمرین برای استفاده آفلاین ذخیره شد.'); }}>
            ⬇ دریافت بسته آفلاین
          </button>
          <button onClick={doSync}>🔄 همگام‌سازی پاسخ‌ها ({faNum(queueLen)} در انتظار)</button>
          {offlineMode && <span className="tag bad">آفلاین: پاسخ مربی و تحلیل گفتار در دسترس نیست؛ تمرین و تصحیح عینی فعال است.</span>}
        </div>
        {err && <p className="err">{err}</p>}
        {user.role === 'parent' || user.role === 'admin'
          ? <ParentPanel setErr={setErr} />
          : <StudentPanel offline={offlineMode} bumpQueue={() => setQueueLen(loadQueue().length)} setErr={setErr} />}
      </main>
    </div>
  );
}

function AuthScreen({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState('student@example.com');
  const [password, setPassword] = useState('Student1234');
  const [name, setName] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [msg, setMsg] = useState('');
  const submit = async () => {
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body = mode === 'login' ? { email, password } : { email, password, full_name: name };
      const r = await api<{ token: string; user: User }>(path, { method: 'POST', body: JSON.stringify(body) });
      setToken(r.token);
      onLogin(r.user);
    } catch (e) { setMsg((e as Error).message); }
  };
  return (
    <main style={{ paddingTop: 40 }}>
      <div className="card" style={{ maxWidth: 460, margin: '0 auto' }}>
        <h1>🎓 مربی هوشمند پایه هشتم</h1>
        <p>سامانه آموزش، تمرین، آزمون و پیگیری پیشرفت — <b>محتوای فعلی نمونه آزمایشی است</b> و پیش از استفاده رسمی نیازمند بازبینی است.</p>
        {mode === 'register' && <p><input placeholder="نام و نام خانوادگی" value={name} onChange={(e) => setName(e.target.value)} /></p>}
        <p><input placeholder="ایمیل" value={email} onChange={(e) => setEmail(e.target.value)} /></p>
        <p><input placeholder="گذرواژه (دست‌کم ۸ نویسه)" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></p>
        {msg && <p className="err">{msg}</p>}
        <button style={{ width: '100%' }} onClick={submit}>{mode === 'login' ? 'ورود' : 'ساخت حساب والد'}</button>
        <p>
          <button className="ghost" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? 'حساب والد ندارم — ثبت‌نام' : 'حساب دارم — ورود'}
          </button>
        </p>
        <div className="note">
          حساب‌های نمایشی توسعه: دانش‌آموز <b>student@example.com / Student1234</b> —
          والد <b>parent@example.com / Parent1234</b>
        </div>
      </div>
    </main>
  );
}

/* ---------------- دانش‌آموز ---------------- */
type Lesson = { id: number; title: string; steps: string[]; example: string; reading_text: string; source: string; review_status: string };
type Question = { id: number; qtype: string; text: string; options: string[]; difficulty: number; hints?: string[] };

function StudentPanel({ offline, bumpQueue, setErr }: { offline: boolean; bumpQueue: () => void; setErr: (s: string) => void }) {
  const [tab, setTab] = useState('home');
  const [tree, setTree] = useState<{ books: unknown[] }>({ books: [] });
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [practice, setPractice] = useState<Question[]>([]);
  const [quizzes, setQuizzes] = useState<{ id: number; title: string; quiz_type: string }[]>([]);
  const [progress, setProgress] = useState<{ mastered: { title: string; mastery: number }[]; need_practice: { title: string; mastery: number }[] } | null>(null);
  const [mistakes, setMistakes] = useState<{ topic_title: string; category: string; count: number }[]>([]);
  const [tasks, setTasks] = useState<{ id: number; title: string; due_date: string; status: string; parent_comment: string }[]>([]);
  const [next, setNext] = useState<{ title?: string; reason?: string } | null>(null);
  const [dueReviews, setDueReviews] = useState<{ title: string }[]>([]);

  const load = useCallback(async () => {
    try {
      const books = await api<{ id: number }[]>('/api/books');
      const trees = await Promise.all(books.map((b) => api(`/api/books/${b.id}/tree`)));
      setTree({ books: trees });
      setQuizzes(await api('/api/quizzes'));
      setProgress(await api('/api/progress'));
      setMistakes(await api('/api/mistakes'));
      setTasks(await api('/api/tasks'));
      setNext(await api('/api/tutor/next'));
      setDueReviews(await api('/api/reviews/due'));
    } catch (e) { setErr((e as Error).message); }
  }, [setErr]);

  useEffect(() => { load(); }, [load]);

  const openLesson = async (lessonId: number, simpler = false) => {
    if (offline) {
      const bundle = loadBundle() as { lessons: Lesson[] } | null;
      const l = bundle?.lessons.find((x) => x.id === lessonId);
      if (l) { setLesson(l); setTab('lesson'); return; }
    }
    setLesson(await api(`/api/lessons/${lessonId}?simpler=${simpler}`));
    setTab('lesson');
  };

  const openPractice = async (topicId: number) => {
    if (offline) {
      const bundle = loadBundle() as { questions: Question[] } | null;
      setPractice((bundle?.questions || []).filter((q) => (q as unknown as { topic_id: number }).topic_id === topicId));
    } else {
      setPractice(await api(`/api/topics/${topicId}/practice`));
    }
    setTab('practice');
  };

  const tabs: [string, string][] = [
    ['home', 'خانه'], ['books', 'درس‌ها'], ['quiz', 'آزمون‌ها'], ['tutor', 'پرسش از مربی'],
    ['mistakes', 'دفتر اشتباهات'], ['tasks', 'تکالیف و برنامه'], ['progress', 'پیشرفت من'],
  ];

  return (
    <div>
      <nav className="tabs">
        {tabs.map(([k, label]) => (
          <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{label}</button>
        ))}
      </nav>

      {tab === 'home' && (
        <div>
          {next?.title && <div className="card"><h2>📌 پیشنهاد مربی برای امروز</h2>
            <b>{next.title}</b><p>{next.reason}</p></div>}
          {dueReviews.length > 0 && <div className="card"><h2>🔁 مرورهای امروز (مرور فاصله‌دار)</h2>
            {dueReviews.map((r, i) => <p key={i}>• {r.title}</p>)}</div>}
          <div className="card"><h2>از کجا شروع کنم؟</h2>
            <p>۱) آزمون تشخیصی بده تا سطح و پیش‌نیازهای ضعیفت مشخص شود. ۲) درس پیشنهادی مربی را بخوان.
               ۳) تمرین هدایت‌شده حل کن. ۴) آزمون مستقل بده؛ پاسخ‌ها تا پایان آزمون نمایش داده نمی‌شوند.</p></div>
        </div>
      )}

      {tab === 'books' && (
        <div>
          {(tree.books as { id: number; title: string; chapters: { id: number; title: string; topics: { id: number; title: string; lesson_id: number | null }[] }[] }[]).map((b) => (
            <div className="card" key={b.id}><h2>📚 {b.title}</h2>
              {b.chapters.map((ch) => (
                <div key={ch.id}><h3>{ch.title}</h3>
                  {ch.topics.map((t) => (
                    <p key={t.id}>• {t.title}{' '}
                      {t.lesson_id && <button className="ghost" onClick={() => openLesson(t.lesson_id!)}>خواندن درس</button>}
                      <button className="ghost" onClick={() => openPractice(t.id)}>تمرین</button>
                    </p>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {tab === 'lesson' && lesson && (
        <LessonView lesson={lesson} offline={offline}
          againSimpler={() => openLesson(lesson.id, true)} setErr={setErr} />
      )}

      {tab === 'practice' && (
        <PracticeView questions={practice} offline={offline} bumpQueue={bumpQueue} setErr={setErr} done={load} />
      )}

      {tab === 'quiz' && <QuizRunner quizzes={quizzes} offline={offline} setErr={setErr} done={load} />}

      {tab === 'tutor' && <TutorChat offline={offline} />}

      {tab === 'mistakes' && (
        <div className="card"><h2>📕 دفتر اشتباهات</h2>
          {mistakes.length === 0 && <p>فعلاً اشتباهی ثبت نشده است. آفرین!</p>}
          {mistakes.map((m, i) => (
            <p key={i}><span className="tag bad">{faNum(m.count)} بار</span> {m.topic_title}
              <small> — دسته: {m.category === 'concept' ? 'مفهومی' : m.category === 'calculation' ? 'محاسباتی' : m.category === 'reading' ? 'خواندن' : 'نامشخص (شواهد کافی نیست)'}</small></p>
          ))}
        </div>
      )}

      {tab === 'tasks' && (
        <div className="card"><h2>🗓 تکالیف و برنامه مطالعه</h2>
          {tasks.map((t) => (
            <p key={t.id}>
              <span className={t.status === 'done' ? 'tag' : 'tag bad'}>{t.status === 'done' ? 'انجام‌شده' : 'در انتظار'}</span>
              {t.title} <small>(سررسید: {t.due_date || '—'})</small>
              {t.parent_comment && <><br /><small>نظر والد: {t.parent_comment}</small></>}
              {t.status !== 'done' && <button className="ghost" onClick={async () => { await api(`/api/tasks/${t.id}/done`, { method: 'POST' }); load(); }}>انجام شد ✓</button>}
            </p>
          ))}
          {tasks.length === 0 && <p>تکلیفی ثبت نشده است.</p>}
        </div>
      )}

      {tab === 'progress' && progress && (
        <div className="card"><h2>📈 پیشرفت من</h2>
          <h3>موضوع‌های تسلط‌یافته</h3>
          {progress.mastered.map((m, i) => <Mastery key={i} title={m.title} v={m.mastery} />)}
          <h3>نیازمند تمرین بیشتر</h3>
          {progress.need_practice.map((m, i) => <Mastery key={i} title={m.title} v={m.mastery} />)}
          {progress.mastered.length + progress.need_practice.length === 0 && <p>هنوز تمرینی ثبت نشده است.</p>}
        </div>
      )}
    </div>
  );
}

function Mastery({ title, v }: { title: string; v: number }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div>{title} — {faNum(Math.round(v * 100))}٪</div>
      <div className="bar-wrap"><div className="bar" style={{ width: `${v * 100}%` }} /></div>
    </div>
  );
}

function LessonView({ lesson, offline, againSimpler, setErr }:
  { lesson: Lesson; offline: boolean; againSimpler: () => void; setErr: (s: string) => void }) {
  const start = useRef(0);
  const [recording, setRecording] = useState<MediaRecorder | null>(null);
  const [audioUrl, setAudioUrl] = useState('');
  const [wpm, setWpm] = useState('');

  const speakSample = () => {
    const u = new SpeechSynthesisUtterance(lesson.reading_text || lesson.example);
    u.lang = 'fa-IR';
    speechSynthesis.speak(u);
  };

  const startRec = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => setAudioUrl(URL.createObjectURL(new Blob(chunks, { type: 'audio/webm' })));
      rec.start();
      start.current = Date.now();
      setRecording(rec);
    } catch { setErr('دسترسی به میکروفون داده نشد. ضبط صدا اختیاری است.'); }
  };

  const stopRec = async () => {
    recording?.stop();
    setRecording(null);
    const seconds = (Date.now() - start.current) / 1000;
    const words = (lesson.reading_text || '').split(/\s+/).filter(Boolean).length;
    if (seconds > 2 && words > 0) {
      const rate = Math.round((words / seconds) * 60);
      setWpm(String(rate));
      await api('/api/reading/records', {
        method: 'POST',
        body: JSON.stringify({ lesson_id: lesson.id, duration_seconds: seconds, words_per_minute: rate }),
      }).catch(() => undefined);
    }
  };

  return (
    <div className="card">
      <h2>{lesson.title}</h2>
      <span className="tag">منبع: {lesson.source}</span>
      <span className="tag">وضعیت بازبینی: {lesson.review_status === 'approved' ? 'تأییدشده' : 'پیش‌نویس آزمایشی'}</span>
      {lesson.steps.map((s, i) => <p key={i}>{s}</p>)}
      {lesson.example && <div className="ok"><b>مثال حل‌شده:</b> {lesson.example}</div>}
      <p>
        <button className="ghost" onClick={againSimpler}>🔁 نفهمیدم؛ ساده‌تر توضیح بده</button>
        {lesson.reading_text && <button className="ghost" onClick={speakSample}>🔊 پخش صوت نمونه (متن‌به‌گفتار دستگاه)</button>}
      </p>
      {lesson.reading_text && (
        <div>
          <h3>🎙 تمرین روان‌خوانی</h3>
          <div className="card" style={{ background: '#f8fafc' }}>{lesson.reading_text}</div>
          <p className="note">ضبط صدا فقط با رضایت والد فعال می‌شود و کاملاً اختیاری است.
            سرعت خواندن (کلمه در دقیقه) از روی مدت ضبط و تعداد کلمه‌های متن محاسبه می‌شود؛ تشخیص خودکار خطای خواندن در این نسخه انجام نمی‌شود.
            {offline && ' در حالت آفلاین تحلیل گفتار در دسترس نیست.'}</p>
          {!recording
            ? <button onClick={startRec}>شروع ضبط (اختیاری)</button>
            : <button className="warn" onClick={stopRec}>توقف ضبط</button>}
          {audioUrl && <p><audio controls src={audioUrl} /></p>}
          {wpm && <p>سرعت تقریبی خواندن تو: <b>{faNum(wpm)} کلمه در دقیقه</b></p>}
        </div>
      )}
    </div>
  );
}

function PracticeView({ questions, offline, bumpQueue, setErr, done }:
  { questions: Question[]; offline: boolean; bumpQueue: () => void; setErr: (s: string) => void; done: () => void }) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [hintLevel, setHintLevel] = useState<Record<number, number>>({});
  const [result, setResult] = useState<Record<number, string>>({});

  const checkOffline = (q: Question) => {
    // تصحیح عینی آفلاین از روی بسته دانلودشده؛ پاسخ در صف همگام‌سازی می‌ماند
    const bundle = loadBundle() as { questions: (Question & { correct_answer: string; explanation: string })[] } | null;
    const full = bundle?.questions.find((x) => x.id === q.id);
    const ok = full && (answers[q.id] || '').trim() === full.correct_answer.trim();
    queueAnswer({ client_id: uid(), question_id: q.id, given_answer: answers[q.id] || '', hints_used: hintLevel[q.id] || 0 });
    bumpQueue();
    setResult((r) => ({ ...r, [q.id]: ok ? `✅ درست بود. ${full.explanation}` : '❌ این پاسخ درست نیست؛ پاسخ در صف همگام‌سازی ذخیره شد.' }));
  };

  if (!questions.length) return <div className="card">برای این موضوع تمرینی نیست یا بسته آفلاین دانلود نشده است.</div>;
  return (
    <div>
      {questions.map((q) => (
        <div className="card" key={q.id}>
          <span className="tag">سطح {faNum(q.difficulty)}</span>
          <b>{q.text}</b>
          {q.options.length > 0
            ? q.options.map((o) => (
              <button key={o} className={`opt ${answers[q.id] === o ? 'sel' : ''}`}
                onClick={() => setAnswers((a) => ({ ...a, [q.id]: o }))}>{o}</button>
            ))
            : <input value={answers[q.id] || ''} onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))} placeholder="پاسخت را بنویس" />}
          <p>
            <button className="ghost" onClick={() => setHintLevel((h) => ({ ...h, [q.id]: Math.min((h[q.id] || 0) + 1, (q.hints || []).length) }))}>
              💡 راهنمایی ({faNum(hintLevel[q.id] || 0)} از {faNum((q.hints || []).length)})
            </button>
            <button onClick={async () => {
              if (offline) return checkOffline(q);
              try {
                const quiz = await api<{ id: number }[]>('/api/quizzes');
                void quiz;
                // تمرین هدایت‌شده: ثبت پاسخ از مسیر همگام‌سازی سرور برای دفتر اشتباهات و مرور
                await api('/api/sync/answers', {
                  method: 'POST',
                  body: JSON.stringify([{ client_id: uid(), question_id: q.id, given_answer: answers[q.id] || '', hints_used: hintLevel[q.id] || 0 }]),
                });
                setResult((r) => ({ ...r, [q.id]: 'پاسخ ثبت شد. برای دیدن بازخورد کامل، آزمون هدایت‌شده بده.' }));
                done();
              } catch (e) {
                queueAnswer({ client_id: uid(), question_id: q.id, given_answer: answers[q.id] || '', hints_used: hintLevel[q.id] || 0 });
                bumpQueue();
                setErr('ارتباط قطع شد؛ پاسخ به‌صورت آفلاین ذخیره شد و بعداً همگام می‌شود.');
              }
            }}>ثبت پاسخ</button>
          </p>
          {(hintLevel[q.id] || 0) > 0 && <div className="note">راهنمایی: {(q.hints || [])[(hintLevel[q.id] || 1) - 1]}</div>}
          {result[q.id] && <div className="ok">{result[q.id]}</div>}
        </div>
      ))}
    </div>
  );
}

function QuizRunner({ quizzes, offline, setErr, done }:
  { quizzes: { id: number; title: string; quiz_type: string }[]; offline: boolean; setErr: (s: string) => void; done: () => void }) {
  const [attempt, setAttempt] = useState<{ attempt_id: number; questions: Question[]; mode: string } | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [final, setFinal] = useState<{ score: number; correct: number; total: number; detail: { question: string; is_correct: boolean; correct_answer: string; explanation: string }[] } | null>(null);

  const start = async (quizId: number, mode: string) => {
    if (offline) { setErr('شروع آزمون آنلاین در حالت آفلاین ممکن نیست؛ از تمرین آفلاین استفاده کن. آزمون‌های از قبل دانلودشده از بخش تمرین‌ها در دسترس‌اند.'); return; }
    const r = await api<{ attempt_id: number; questions: Question[]; mode: string }>('/api/attempts', {
      method: 'POST', body: JSON.stringify({ quiz_id: quizId, mode }),
    });
    setAttempt(r); setFinal(null); setAnswers({});
  };

  const finish = async () => {
    if (!attempt) return;
    for (const q of attempt.questions) {
      await api(`/api/attempts/${attempt.attempt_id}/answers`, {
        method: 'POST',
        body: JSON.stringify({ question_id: q.id, given_answer: answers[q.id] || '', client_id: uid() }),
      });
    }
    const r = await api('/api/attempts/' + attempt.attempt_id + '/submit', { method: 'POST' });
    setFinal(r as never);
    done();
  };

  if (final) return (
    <div className="card"><h2>نتیجه آزمون: {faNum(final.score)} از ۱۰۰</h2>
      <p>{faNum(final.correct)} پاسخ درست از {faNum(final.total)} سؤال</p>
      {final.detail.map((d, i) => (
        <div key={i} className={d.is_correct ? 'ok' : 'err'} style={{ marginBottom: 8 }}>
          <b>{d.question}</b><br />پاسخ درست: {d.correct_answer}<br /><small>{d.explanation}</small>
        </div>
      ))}
      <button onClick={() => { setAttempt(null); setFinal(null); }}>بازگشت به فهرست آزمون‌ها</button>
    </div>
  );

  if (attempt) return (
    <div>
      <div className="note">{attempt.mode === 'independent'
        ? 'آزمون مستقل: پاسخ درست تا پایان آزمون نمایش داده نمی‌شود.'
        : 'تمرین با کمک مربی: می‌توانی از راهنمایی استفاده کنی.'}</div>
      {attempt.questions.map((q) => (
        <div className="card" key={q.id}><b>{q.text}</b>
          {q.options.length > 0
            ? q.options.map((o) => (
              <button key={o} className={`opt ${answers[q.id] === o ? 'sel' : ''}`}
                onClick={() => setAnswers((a) => ({ ...a, [q.id]: o }))}>{o}</button>
            ))
            : <input value={answers[q.id] || ''} onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))} placeholder="پاسخت" />}
        </div>
      ))}
      <button onClick={finish}>پایان آزمون و دیدن نتیجه</button>
    </div>
  );

  return (
    <div className="grid">
      {quizzes.map((q) => (
        <div className="card" key={q.id}><h3>{q.title}</h3>
          <span className="tag">{q.quiz_type === 'diagnostic' ? 'تشخیصی' : q.quiz_type}</span>
          <p>
            <button onClick={() => start(q.id, 'independent')}>شروع آزمون مستقل</button>{' '}
            <button className="ghost" onClick={() => start(q.id, 'guided')}>تمرین با کمک مربی</button>
          </p>
        </div>
      ))}
    </div>
  );
}

function TutorChat({ offline }: { offline: boolean }) {
  const [q, setQ] = useState('');
  const [log, setLog] = useState<{ who: string; text: string }[]>([]);
  const ask = async () => {
    if (offline) {
      setLog((l) => [...l, { who: 'من', text: q }, { who: 'مربی', text: 'در حالت آفلاین پاسخ‌گویی مربی در دسترس نیست؛ درس‌های دانلودشده و تمرین‌ها فعال‌اند.' }]);
      setQ('');
      return;
    }
    const my = q; setQ('');
    setLog((l) => [...l, { who: 'من', text: my }]);
    const r = await api<{ answer: string; confident: boolean }>('/api/tutor/ask', {
      method: 'POST', body: JSON.stringify({ question: my }),
    });
    setLog((l) => [...l, { who: 'مربی', text: r.answer }]);
  };
  return (
    <div className="card"><h2>🤖 پرسش از مربی</h2>
      <p className="note">مربی فقط از محتوای موجود و بازبینی‌پذیر پاسخ می‌دهد و اگر مطمئن نباشد، صریح می‌گوید نمی‌دانم.</p>
      {log.map((m, i) => <p key={i}><b>{m.who}:</b> {m.text}</p>)}
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="سؤالت را بپرس؛ مثلاً: عدد اول چیست؟"
        onKeyDown={(e) => e.key === 'Enter' && ask()} />
      <p><button onClick={ask} disabled={!q.trim()}>بپرس</button></p>
    </div>
  );
}

/* ---------------- والد ---------------- */
function ParentPanel({ setErr }: { setErr: (s: string) => void }) {
  const [students, setStudents] = useState<User[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [period, setPeriod] = useState('weekly');
  const [report, setReport] = useState<{
    approx_study_minutes: number; practice_answers: number; avg_score: number | null;
    tasks_done: number; tasks_total: number; note: string;
    frequent_mistakes: { topic: string; count: number }[];
    quiz_scores: { score: number; mode: string }[];
  } | null>(null);
  const [taskTitle, setTaskTitle] = useState('');
  const [due, setDue] = useState('');
  const [newStudent, setNewStudent] = useState({ email: '', full_name: '', password: '' });
  const [msg, setMsg] = useState('');

  const loadStudents = useCallback(async () => {
    const s = await api<User[]>('/api/parent/students');
    setStudents(s);
    if (s.length && sel === null) setSel(s[0].id);
  }, [sel]);

  useEffect(() => { loadStudents().catch((e) => setErr(e.message)); }, [loadStudents, setErr]);

  useEffect(() => {
    if (sel) api(`/api/parent/students/${sel}/report?period=${period}`).then(setReport as never).catch((e) => setErr(e.message));
  }, [sel, period, setErr]);

  const createStudent = async () => {
    await api('/api/parent/students', { method: 'POST', body: JSON.stringify(newStudent) });
    setMsg('حساب دانش‌آموز ساخته شد.');
    loadStudents();
  };

  const assignTask = async () => {
    if (!sel) return;
    await api('/api/tasks', { method: 'POST', body: JSON.stringify({ student_id: sel, title: taskTitle, due_date: due }) });
    setMsg('تکلیف ثبت و برای دانش‌آموز ارسال شد.');
    setTaskTitle('');
  };

  const comment = async (taskId: number, text: string) => {
    await api(`/api/tasks/${taskId}/comment`, { method: 'POST', body: JSON.stringify({ student_id: sel, text }) });
    setMsg('نظر شما ثبت شد.');
  };

  const toggleVoice = async (student: User) => {
    await api(`/api/parent/students/${student.id}/voice-consent?allowed=${!student.voice_recording_allowed}`, { method: 'POST' });
    loadStudents();
  };

  const tasksOf = async () => {
    if (!sel) return;
    const t = await api<{ id: number; title: string; status: string }[]>(`/api/tasks?student_id=${sel}`);
    return t;
  };
  const [taskList, setTaskList] = useState<{ id: number; title: string; status: string }[]>([]);
  useEffect(() => { tasksOf().then((t) => t && setTaskList(t)); }, [sel]); // eslint-disable-line

  return (
    <div>
      <div className="card"><h2>👨‍👩‍👧 دانش‌آموزان من</h2>
        {students.map((s) => (
          <p key={s.id}>
            <button className={sel === s.id ? '' : 'ghost'} onClick={() => setSel(s.id)}>{s.full_name}</button>
            <small> {s.email} — ضبط صدا: {s.voice_recording_allowed ? 'مجاز (با رضایت شما)' : 'غیرفعال'}</small>
            <button className="ghost" onClick={() => toggleVoice(s)}>
              {s.voice_recording_allowed ? 'خاموش‌کردن ضبط صدا' : 'روشن‌کردن ضبط صدا با رضایت من'}
            </button>
          </p>
        ))}
        <h3>ساخت حساب دانش‌آموز جدید</h3>
        <input placeholder="نام دانش‌آموز" value={newStudent.full_name} onChange={(e) => setNewStudent({ ...newStudent, full_name: e.target.value })} />
        <input placeholder="ایمیل دانش‌آموز" value={newStudent.email} onChange={(e) => setNewStudent({ ...newStudent, email: e.target.value })} />
        <input placeholder="گذرواژه (دست‌کم ۸ نویسه)" type="password" value={newStudent.password} onChange={(e) => setNewStudent({ ...newStudent, password: e.target.value })} />
        <p><button onClick={createStudent}>ساخت حساب</button></p>
        {msg && <p className="ok">{msg}</p>}
      </div>

      {report && (
        <div className="card"><h2>📊 گزارش پیشرفت</h2>
          <p>
            <button className={period === 'daily' ? '' : 'ghost'} onClick={() => setPeriod('daily')}>روزانه</button>{' '}
            <button className={period === 'weekly' ? '' : 'ghost'} onClick={() => setPeriod('weekly')}>هفتگی</button>
          </p>
          <p>زمان تقریبی فعالیت در برنامه: <b>{faNum(report.approx_study_minutes)} دقیقه</b></p>
          <p className="note">{report.note}</p>
          <p>تعداد پاسخ‌های تمرینی: <b>{faNum(report.practice_answers)}</b> —
             میانگین نمره آزمون‌ها: <b>{report.avg_score === null ? '—' : faNum(report.avg_score)}</b> —
             تکلیف انجام‌شده: <b>{faNum(report.tasks_done)} از {faNum(report.tasks_total)}</b></p>
          <h3>روند نمره‌ها</h3>
          {report.quiz_scores.map((s, i) => (
            <div key={i} style={{ marginBottom: 8 }}>
              <div>{s.mode === 'guided' ? 'با کمک مربی' : 'مستقل'} — {faNum(s.score)}٪</div>
              <div className="bar-wrap"><div className="bar" style={{ width: `${s.score}%` }} /></div>
            </div>
          ))}
          <h3>اشتباهات پرتکرار و درس‌های نیازمند توجه</h3>
          {report.frequent_mistakes.map((m, i) => <p key={i}>• {m.topic} — {faNum(m.count)} بار</p>)}
          {report.frequent_mistakes.length === 0 && <p>موردی ثبت نشده است.</p>}
        </div>
      )}

      <div className="card"><h2>🗓 تعیین تکلیف و برنامه مطالعه</h2>
        <input placeholder="عنوان تکلیف؛ مثلاً: تمرین جمع و تفریق عددهای صحیح" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} />
        <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        <p><button onClick={assignTask} disabled={!taskTitle.trim()}>ثبت تکلیف</button></p>
        {taskList.map((t) => (
          <p key={t.id}><span className={t.status === 'done' ? 'tag' : 'tag bad'}>{t.status === 'done' ? 'انجام‌شده' : 'در انتظار'}</span>{t.title}
            <button className="ghost" onClick={() => { const txt = prompt('نظر شما درباره این تکلیف:'); if (txt) comment(t.id, txt); }}>ثبت نظر والد</button>
          </p>
        ))}
      </div>

      <div className="card"><h2>🔒 حریم خصوصی</h2>
        <p>ضبط صدای دانش‌آموز فقط با رضایت شما فعال می‌شود و هر زمان از همین پنل قابل خاموش‌کردن است.
           داده‌های جمع‌آوری‌شده به حداقل لازم محدود است. حذف حساب و داده‌ها از مسیر پشتیبانی/مدیر سامانه انجام می‌شود (docs/PRIVACY.md).</p>
      </div>
    </div>
  );
}
