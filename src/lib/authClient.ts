import { buildApiUrl } from './apiClient';

/**
 * 带认证的fetch函数
 * 自动添加Session Token到请求头
 */
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = localStorage.getItem('session_token');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers['X-Session-Token'] = token;
  }

  return fetch(buildApiUrl(url), {
    ...options,
    headers,
    credentials: 'include', // 支持cookie
  });
}

/**
 * 带认证的GET请求
 */
export async function authenticatedGet(url: string): Promise<Response> {
  return authenticatedFetch(url, { method: 'GET' });
}

/**
 * 带认证的POST请求
 */
export async function authenticatedPost(
  url: string,
  data: any
): Promise<Response> {
  return authenticatedFetch(url, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * 带认证的PUT请求
 */
export async function authenticatedPut(
  url: string,
  data: any
): Promise<Response> {
  return authenticatedFetch(url, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * 带认证的DELETE请求
 */
export async function authenticatedDelete(url: string): Promise<Response> {
  return authenticatedFetch(url, { method: 'DELETE' });
}

/**
 * 上报用户有没有照推荐去学（adaptive_recommendation.is_accepted / actual_choice）。
 * 只用于统计推荐准不准：不等待、失败不影响学习流程；keepalive 让紧接着的跳转不打断它。
 * 照推荐建学习会话时后端也会补记采纳，这个请求丢了也不影响「采纳」与推荐效果。
 * actualChoice 记实际去学的，如 'word:17'、'today-review'。
 */
export function sendRecommendationFeedback(
  userId: string,
  recommendationId: number | null | undefined,
  accepted: boolean,
  actualChoice: string
): void {
  if (!recommendationId) return;
  authenticatedFetch('/api/adaptive/feedback', {
    method: 'POST',
    body: JSON.stringify({ userId, recommendationId, accepted, actualChoice }),
    keepalive: true
  }).catch(() => {
    /* 统计数据，丢了不影响使用 */
  });
}
