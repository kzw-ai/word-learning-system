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

/** 取本设备的访客 ID，没有就生成；每次都重写 cookie，防止被单独清掉 */
export const ensureGuestId = (): string => {
  let id: string | null = null;
  try {
    id = window.localStorage.getItem(GUEST_STORAGE_KEY);
  } catch {
    // 隐私模式等情况下 localStorage 不可用：本次访问用一个临时 ID
  }
  if (!isGuestId(id)) {
    id = generateGuestId();
    try {
      window.localStorage.setItem(GUEST_STORAGE_KEY, id);
    } catch {
      // 同上
    }
  }
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
