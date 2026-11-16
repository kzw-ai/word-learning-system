import { storedGuestId } from './guestIdentity';

const TOKEN_STORAGE_KEY = 'session_token';

/** 登录用户的 session token；没有则为 null（读 localStorage，容错） */
export const getSessionToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
};

/** 未登录访客的 guest id；没有则为 null（复用 guestIdentity 的本地存储逻辑） */
export const getGuestId = (): string | null => {
  if (typeof window === 'undefined') return null;
  return storedGuestId();
};

/**
 * 身份请求头：登录用户带 X-Session-Token，访客带 X-Guest-Id，都没有则为空对象。
 * 前后端不同源（App 里页面来源是 capacitor://localhost / https://localhost）时，
 * cookie 不会跟着请求走，必须靠这两个头让后端认身份。
 * 抽成独立模块，避免 authClient 与 apiClient 互相引用形成循环依赖。
 */
export const getAuthHeaders = (): Record<string, string> => {
  const token = getSessionToken();
  if (token) return { 'X-Session-Token': token };
  const guestId = getGuestId();
  if (guestId) return { 'X-Guest-Id': guestId };
  return {};
};
