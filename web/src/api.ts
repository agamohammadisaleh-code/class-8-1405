// لایه ارتباط با سرور + صف آفلاین (پاسخ‌ها روی دستگاه می‌مانند تا همگام‌سازی)
export type User = {
  id: number; email: string; full_name: string; role: string;
  voice_recording_allowed: boolean;
};

const TOKEN_KEY = 'morabi_token';
const QUEUE_KEY = 'morabi_offline_queue';
const BUNDLE_KEY = 'morabi_offline_bundle';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let msg = 'خطای ارتباط با سرور';
    try { msg = (await res.json()).detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

export type QueuedAnswer = {
  client_id: string; question_id: number; given_answer: string; hints_used: number;
};

export const loadQueue = (): QueuedAnswer[] => {
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); } catch { return []; }
};

export function queueAnswer(a: QueuedAnswer) {
  const q = loadQueue();
  if (!q.some((x) => x.client_id === a.client_id)) {
    q.push(a);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  }
  return q.length;
}

export async function syncQueue(): Promise<{ saved: number; duplicates_ignored: number } | null> {
  const q = loadQueue();
  if (!q.length) return null;
  const r = await api<{ saved: number; duplicates_ignored: number }>('/api/sync/answers', {
    method: 'POST', body: JSON.stringify(q),
  });
  localStorage.removeItem(QUEUE_KEY);
  return r;
}

export async function downloadBundle() {
  const bundle = await api<unknown>('/api/content/download-bundle');
  localStorage.setItem(BUNDLE_KEY, JSON.stringify(bundle));
  return bundle;
}

export const loadBundle = () => {
  try { return JSON.parse(localStorage.getItem(BUNDLE_KEY) || 'null'); } catch { return null; }
};

export const uid = () =>
  (crypto as Crypto).randomUUID ? crypto.randomUUID() : `id-${Date.now()}-${Math.random()}`;
