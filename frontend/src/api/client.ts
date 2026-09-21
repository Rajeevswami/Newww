export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  is_verified: boolean;
  tenant: { id: string; name: string; slug: string; plan: string };
};
export type Job = {
  id: string;
  title: string;
  department: string;
  description: string;
  required_skills: string[];
  experience_level: string;
  location: string;
  employment_type: string;
  salary: string;
  status: string;
  created_at: string;
  applicants: number;
};
export type Resume = {
  id: string;
  filename: string;
  status?: string;
  parsed_json: { name: string; skills: string[]; experience: string[]; education: string[]; summary: string };
  created_at: string;
};
export type Application = {
  id: string;
  name: string;
  email: string;
  job_id: string;
  job_title: string;
  department: string;
  match_score: number | null;
  status: string;
  created_at: string;
  resume: Resume['parsed_json'];
};
export type Scorecard = {
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  recommendation: string;
  summary: string;
  mode: string;
};
export type Interview = {
  id: string;
  application_id: string;
  name?: string;
  job_title?: string;
  status: string;
  transcript_json: { role: string; content: string; evaluation?: { feedback: string; score: number } }[];
  scorecard_json: Scorecard | null;
  started_at: string;
};
export type Analytics = {
  active_jobs: number;
  applications: number;
  application_change: number | null;
  interviews: number;
  average_match: number;
  shortlisted: number;
  completed_interviews: number;
  new_jobs: number;
  ai_mode: string;
  series: { date: string; applications: number; shortlisted: number }[];
  funnel: { name: string; value: number }[];
};
export type Session = {
  access_token: string;
  user: User;
  demo: boolean;
  ai_mode: string;
  verification_token?: string;
};
let accessToken = '';
let refreshing: Promise<Session> | null = null;
export function setToken(token: string) {
  accessToken = token;
}
export function getToken() {
  return accessToken;
}
export async function api<T = any>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    ...(options.headers as Record<string, string>),
  };
  const response = await fetch(`/api${path}`, { ...options, headers, credentials: 'include' });
  if (
    response.status === 401 &&
    retry &&
    (!path.startsWith('/auth/') || path === '/auth/logout' || path === '/auth/me')
  ) {
    try {
      refreshing ??= api<Session>('/auth/refresh', { method: 'POST' }, false).finally(() => {
        refreshing = null;
      });
      const session = await refreshing;
      setToken(session.access_token);
      return api(path, options, false);
    } catch {
      window.dispatchEvent(new Event('session-expired'));
    }
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((e: { msg: string; loc: string[] }) => `${e.loc.slice(1).join(' ')}: ${e.msg}`)
              .join('; ')
          : 'Something went wrong. Please try again.',
    );
  }
  return data as T;
}
export const post = <T = any>(path: string, data?: unknown) =>
  api<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) });
export function exportCSV(rows: Record<string, unknown>[], filename: string) {
  if (!rows.length) return;
  void post('/activity/export').catch(() => {});
  const columns = Object.keys(rows[0]);
  const cell = (value: unknown) => {
    const text = String(value ?? '');
    return '"' + (/^[=+@\-\t\r]/.test(text) ? "'" : '') + text.replaceAll('"', '""') + '"';
  };
  const csv = [
    columns.map(cell).join(','),
    ...rows.map((row) => columns.map((k) => cell(row[k])).join(',')),
  ].join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' }));
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
