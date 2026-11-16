// 源文件：src/lib/authClient.ts（网页版）。RN 版：去掉 credentials/keepalive（RN 无 cookie 概念），
// 其余结构照搬。
import { buildApiUrl } from './apiClient';
import { getAuthHeaders } from './authHeaders';

/** 带认证的 fetch：自动加 X-Session-Token / X-Guest-Id 请求头 */
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(await getAuthHeaders()),
    ...((options.headers as Record<string, string>) || {}),
  };

  return fetch(buildApiUrl(url), {
    ...options,
    headers,
  });
}

export async function authenticatedGet(url: string): Promise<Response> {
  return authenticatedFetch(url, { method: 'GET' });
}

export async function authenticatedPost(url: string, data: unknown): Promise<Response> {
  return authenticatedFetch(url, { method: 'POST', body: JSON.stringify(data) });
}

export async function authenticatedPut(url: string, data: unknown): Promise<Response> {
  return authenticatedFetch(url, { method: 'PUT', body: JSON.stringify(data) });
}

export async function authenticatedDelete(url: string): Promise<Response> {
  return authenticatedFetch(url, { method: 'DELETE' });
}

/** 上报用户有没有照推荐去学。只用于统计：不等待、失败不影响学习流程。 */
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
  }).catch(() => {
    /* 统计数据，丢了不影响使用 */
  });
}
