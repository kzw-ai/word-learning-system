// 源文件：src/lib/authHeaders.ts（网页版）。RN 版：token/guest id 从 SecureStore/AsyncStorage 读，
// 因此 getAuthHeaders 是异步的（网页版 localStorage 是同步的）。
import { getSecure } from './storage';
import { storedGuestId } from './guestIdentity';

const TOKEN_STORAGE_KEY = 'session_token';

/** 登录用户的 session token；没有则为 null */
export const getSessionToken = (): Promise<string | null> => getSecure(TOKEN_STORAGE_KEY);

/** 未登录访客的 guest id；没有则为 null */
export const getGuestId = (): Promise<string | null> => storedGuestId();

/**
 * 身份请求头：登录用户带 X-Session-Token，访客带 X-Guest-Id，都没有则为空对象。
 * RN 发请求不受浏览器跨域规则限制，也不依赖 cookie，必须靠这两个头让后端认身份。
 */
export const getAuthHeaders = async (): Promise<Record<string, string>> => {
  const token = await getSessionToken();
  if (token) return { 'X-Session-Token': token };
  const guestId = await getGuestId();
  if (guestId) return { 'X-Guest-Id': guestId };
  return {};
};
