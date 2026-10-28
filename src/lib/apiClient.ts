import type { ExerciseSetResponse, RecentSessionSummary, UserProfileSummary, WordResponse, WordSummary } from './types';
import { storedGuestId } from './guestIdentity';

const getDefaultBase = () => {
  const envBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_BASE_URL;
  if (envBase !== undefined && envBase !== '') {
    return envBase.replace(/\/$/, '');
  }
  // In browser: use relative paths (same domain, proxied by Nginx)
  // On server (SSR): use direct backend URL
  if (typeof window !== 'undefined') {
    return '';
  }
  return 'http://localhost:5004';
};
const DEFAULT_BASE = getDefaultBase();
const STORAGE_KEY = 'learningSystem.apiBaseUrl';

let runtimeOverride: string | null = null;

const sanitizeBaseUrl = (value: string) => value.replace(/\/$/, '');

export const getDefaultApiBaseUrl = () => DEFAULT_BASE;

export const setApiBaseUrlOverride = (value: string | null) => {
  runtimeOverride = value ? sanitizeBaseUrl(value) : null;
  if (typeof window !== 'undefined') {
    if (runtimeOverride) {
      window.localStorage.setItem(STORAGE_KEY, runtimeOverride);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }
};

const readStoredBaseUrl = () => {
  if (typeof window === 'undefined') {
    return runtimeOverride;
  }

  if (runtimeOverride) {
    return runtimeOverride;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored) {
    runtimeOverride = sanitizeBaseUrl(stored);
    return runtimeOverride;
  }

  return null;
};

export const getApiBaseUrl = () => readStoredBaseUrl() ?? DEFAULT_BASE;

export const buildApiUrl = (path: string) => {
  const baseUrl = getApiBaseUrl();
  if (!path) {
    return baseUrl;
  }
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalized}`;
};

export const fetchJson = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(buildApiUrl(path), init);
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
};

export const fetchWord = (wordId: number | string) => fetchJson<WordResponse>(`/word/${wordId}`);

export const fetchWords = () => fetchJson<WordSummary[]>('/words');

export const fetchWordExercises = async (
  wordId: number | string,
  params?: { limit?: number; options?: number }
) => {
  const searchParams = new URLSearchParams();
  if (params?.limit) {
    searchParams.set('limit', String(params.limit));
  }
  if (params?.options) {
    searchParams.set('options', String(params.options));
  }

  const query = searchParams.toString();
  const suffix = query ? `?${query}` : '';
  // 带上身份：学习期的复习只出还需复习的题型，后端要认得出是谁。登录用户带 token，
  // 访客带 X-Guest-Id（前后端不在同一主机时访客 cookie 不会跟着请求走）。
  // 不走 authenticatedFetch 是因为 authClient 依赖本文件，反过来引用会形成循环依赖
  const headers: Record<string, string> = {};
  if (typeof window !== 'undefined') {
    let token: string | null = null;
    try {
      token = window.localStorage.getItem('session_token');
    } catch {
      token = null;
    }
    if (token) headers['X-Session-Token'] = token;
    const guestId = storedGuestId();
    if (guestId) headers['X-Guest-Id'] = guestId;
  }
  const result = await fetchJson<{ success: boolean; data: ExerciseSetResponse; error?: string }>(
    `/api/learning/word/${wordId}/exercises${suffix}`,
    { credentials: 'include', headers }
  );

  if (!result.success || !result.data) {
    throw new Error(result.error || 'Failed to fetch exercises');
  }

  return result.data;
};

export const fetchUsers = async (params?: { limit?: number; search?: string }) => {
  const searchParams = new URLSearchParams();
  if (params?.limit) {
    searchParams.set('limit', String(params.limit));
  }
  if (params?.search) {
    searchParams.set('search', params.search);
  }

  const query = searchParams.toString();
  const suffix = query ? `?${query}` : '';
  const result = await fetchJson<{ success: boolean; data: UserProfileSummary[]; error?: string }>(
    `/api/users${suffix}`
  );

  if (!result.success || !Array.isArray(result.data)) {
    throw new Error(result.error || 'Failed to fetch users');
  }

  return result.data;
};

export const fetchRecentSessions = async (userId: string, params?: { limit?: number }) => {
  const searchParams = new URLSearchParams();
  if (params?.limit) {
    searchParams.set('limit', String(params.limit));
  }
  const query = searchParams.toString();
  const suffix = query ? `?${query}` : '';
  const result = await fetchJson<{ success: boolean; data: RecentSessionSummary[]; error?: string }>(
    `/api/users/${userId}/sessions/recent${suffix}`
  );
  if (!result.success || !Array.isArray(result.data)) {
    throw new Error(result.error || 'Failed to fetch recent sessions');
  }
  return result.data;
};

// 学习状态持久化（跨设备恢复）
export interface LearningStateData {
  wordId?: number | null;
  word?: string | null;
  module?: string | null;
  vksLevel?: string | null;
  recommendationId?: number | null;
  lastUpdated?: string | null;
}

export const fetchLearningState = async (userId: string): Promise<LearningStateData> => {
  const result = await fetchJson<{ success: boolean; data: LearningStateData; error?: string }>(
    `/api/users/${userId}/learning-state`
  );
  if (!result.success) {
    throw new Error(result.error || 'Failed to fetch learning state');
  }
  return result.data;
};

export const saveLearningState = async (userId: string, state: Partial<LearningStateData>): Promise<void> => {
  await fetchJson<{ success: boolean; error?: string }>(
    `/api/users/${userId}/learning-state`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state)
    }
  );
};
