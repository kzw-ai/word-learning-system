// 源文件：src/lib/guestIdentity.ts（网页版）。RN 版：随机源用 expo-crypto，
// 存储用 AsyncStorage（卸载即清，重装即新访客）。
import * as Crypto from 'expo-crypto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getLocal, setLocal } from './storage';

/**
 * 未登录访客的身份。每台设备首次启动时生成一个随机 ID，持久保存，
 * 请求时放在 X-Guest-Id 头里。随机串本身就是凭证：足够长、猜不到。
 * ID 以 guest_ 开头，后端据此区分访客和注册用户；注册时后端把访客记录并入新账号。
 */
const GUEST_STORAGE_KEY = 'learningSystem.guestId';
const GUEST_ID_PATTERN = /^guest_[A-Za-z0-9]{16,64}$/;
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

export const isGuestId = (id: string | null | undefined): id is string =>
  Boolean(id) && GUEST_ID_PATTERN.test(id as string);

const generateGuestId = (): string => {
  const bytes = new Uint8Array(20);
  Crypto.getRandomValues(bytes);
  // 62 种字符取模的偏差可以忽略：这里要的是不可猜，不是均匀分布
  return 'guest_' + Array.from(bytes, b => ALPHABET[b % ALPHABET.length]).join('');
};

/** 本设备已有的访客 ID，没有返回 null（不生成） */
export const storedGuestId = async (): Promise<string | null> => {
  const id = await getLocal(GUEST_STORAGE_KEY);
  return isGuestId(id) ? id : null;
};

/** 本设备此前是否已有访客 ID */
export const hasStoredGuestId = async (): Promise<boolean> => {
  const id = await getLocal(GUEST_STORAGE_KEY);
  return isGuestId(id);
};

/** 取本设备的访客 ID，没有就生成并持久保存 */
export const ensureGuestId = async (): Promise<string> => {
  let stored: string | null;
  try {
    stored = await AsyncStorage.getItem(GUEST_STORAGE_KEY);
  } catch {
    // 读失败不等于没有：不能生成新 ID 把原来的覆盖掉（覆盖后原访客的学习记录就再也找不回来）。
    // 这次先用一个临时 ID、不写入；下次启动读成功，还是原来的身份。
    return generateGuestId();
  }
  if (isGuestId(stored)) return stored;
  const id = generateGuestId();
  await setLocal(GUEST_STORAGE_KEY, id);
  return id;
};

/** 界面上显示的访客名，如「Learner 4821」；由 ID 稳定推出，同一设备始终一致 */
export const guestDisplayName = (id: string) => {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return `Learner ${1000 + (hash % 9000)}`;
};
