/**
 * 未登录访客的身份。
 *
 * 每台设备（浏览器）首次访问时生成一个随机 ID，存在 localStorage，并写进 cookie
 * 随同源请求自动发送给后端。随机串本身就是凭证：足够长、猜不到，所以别人无法
 * 冒充。此前所有未登录访客共用 test_user_001，学习记录会混在一起。
 *
 * ID 以 guest_ 开头，后端与数据分析据此区分访客和注册用户；注册时后端会把
 * 访客名下的学习数据并入新账号。
 */

const GUEST_STORAGE_KEY = 'learningSystem.guestId';
const GUEST_COOKIE = 'guest_id';
const GUEST_ID_PATTERN = /^guest_[A-Za-z0-9]{16,64}$/;
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

export const isGuestId = (id: string | null | undefined): id is string =>
  Boolean(id) && GUEST_ID_PATTERN.test(id as string);

/** localStorage 读写的容错封装：隐私模式、站点数据被禁用时访问会直接抛错 */
export const safeGetItem = (key: string): string | null => {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

export const safeSetItem = (key: string, value: string) => {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 存不下就只在本次页面生命周期内有效
  }
};

export const safeRemoveItem = (key: string) => {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // 同上
  }
};

// 本页面生命周期内的访客 ID。localStorage 不可用时，没有它每次调用都会生成新 ID
let cachedGuestId: string | null = null;

/** 本设备此前是否已有访客 ID（用于判断是不是第一次以访客身份访问） */
export const hasStoredGuestId = () => isGuestId(safeGetItem(GUEST_STORAGE_KEY));

const generateGuestId = () => {
  const bytes = new Uint8Array(20);
  window.crypto.getRandomValues(bytes);
  // 62 种字符取模的偏差可以忽略：这里要的是不可猜，不是均匀分布
  return 'guest_' + Array.from(bytes, b => ALPHABET[b % ALPHABET.length]).join('');
};

const writeGuestCookie = (id: string) => {
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `${GUEST_COOKIE}=${id}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
};

/** 本设备已有的访客 ID，没有返回 null（不生成）。前后端不在同一主机时 cookie 不会跟着请求走，
 * 需要身份的请求用它带上 X-Guest-Id */
export const storedGuestId = (): string | null => {
  const id = safeGetItem(GUEST_STORAGE_KEY);
  return isGuestId(id) ? id : isGuestId(cachedGuestId) ? cachedGuestId : null;
};

/** 取本设备的访客 ID，没有就生成；每次都重写 cookie，防止被单独清掉 */
export const ensureGuestId = (): string => {
  let id = safeGetItem(GUEST_STORAGE_KEY);
  if (!isGuestId(id)) {
    id = isGuestId(cachedGuestId) ? cachedGuestId : generateGuestId();
    safeSetItem(GUEST_STORAGE_KEY, id);
  }
  cachedGuestId = id;
  writeGuestCookie(id);
  return id;
};

/** 界面上显示的访客名，如「学习者 4821」；由 ID 稳定推出，同一设备始终一致 */
export const guestDisplayName = (id: string) => {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return `学习者 ${1000 + (hash % 9000)}`;
};
