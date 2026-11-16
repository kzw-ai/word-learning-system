// 源文件：src/lib/apiClient.ts（网页版）。RN 版：base URL 用 EXPO_PUBLIC_API_BASE_URL 或默认本地后端，
// 去掉 window/localStorage/SSR 分支，保留相对路径拼接逻辑。
import type {
  ExerciseSetResponse,
  RecentSessionSummary,
  UserProfileSummary,
  WordResponse,
  WordSummary,
} from './types';
import { getAuthHeaders } from './authHeaders';

// 开发期（__DEV__）默认连本地后端（iOS 模拟器 127.0.0.1；安卓模拟器先 adb reverse tcp:5014 tcp:5014）；
// 正式包默认连线上，避免忘了设 EXPO_PUBLIC_API_BASE_URL 时连到用户手机的本机地址。
// 真机通过 EXPO_PUBLIC_API_BASE_URL 环境变量指到 Mac 的局域网地址。
const LOCAL_BASE = 'http://127.0.0.1:5014';
const PROD_BASE = 'https://learnchinese.kzwbelieve.top';

/** 计算默认后端地址：环境变量优先；否则开发包用本地后端、正式包用线上。 */
export const resolveDefaultBase = (dev: boolean, envBase?: string): string => {
  if (envBase && envBase !== '') return envBase.replace(/\/$/, '');
  return dev ? LOCAL_BASE : PROD_BASE;
};

const envBase = process.env.EXPO_PUBLIC_API_BASE_URL;
const DEFAULT_BASE = resolveDefaultBase(typeof __DEV__ === 'undefined' || __DEV__, envBase);

let baseUrl = DEFAULT_BASE;

export const getDefaultApiBaseUrl = () => DEFAULT_BASE;

export const setApiBaseUrl = (url: string | null) => {
  baseUrl = url && url !== '' ? url.replace(/\/$/, '') : DEFAULT_BASE;
};

export const getApiBaseUrl = () => baseUrl;

export const buildApiUrl = (path: string) => {
  if (!path) return baseUrl;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalized}`;
};

export const fetchJson = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      ...(await getAuthHeaders()),
      ...(init?.headers as Record<string, string> | undefined),
    },
  });
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
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.options) searchParams.set('options', String(params.options));
  const query = searchParams.toString();
  const suffix = query ? `?${query}` : '';
  const result = await fetchJson<{ success: boolean; data: ExerciseSetResponse; error?: string }>(
    `/api/learning/word/${wordId}/exercises${suffix}`
  );
  if (!result.success || !result.data) {
    throw new Error(result.error || 'Failed to fetch exercises');
  }
  return result.data;
};

export const fetchUsers = async (params?: { limit?: number; search?: string }) => {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.search) searchParams.set('search', params.search);
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
  if (params?.limit) searchParams.set('limit', String(params.limit));
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
      body: JSON.stringify(state),
    }
  );
};

/** 学习者选等级：3（三级词）或 4（四级词） */
export const saveHskLevel = async (userId: string, level: 3 | 4): Promise<void> => {
  const result = await fetchJson<{ success: boolean; error?: string }>(
    `/api/users/${userId}/hsk-level`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level }),
    }
  );
  if (!result.success) {
    throw new Error(result.error || 'Failed to save level');
  }
};
