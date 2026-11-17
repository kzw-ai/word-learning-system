/* eslint-disable import/first -- jest.mock 必须在 import 之前 */
jest.mock('expo-crypto', () => ({
  getRandomValues: (arr: Uint8Array) => {
    for (let i = 0; i < arr.length; i += 1) arr[i] = i;
    return arr;
  },
}));
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve(null)),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(() => Promise.resolve(null)),
  setItem: jest.fn(() => Promise.resolve()),
  removeItem: jest.fn(() => Promise.resolve()),
}));

import AsyncStorage from '@react-native-async-storage/async-storage';
import { isGuestId, guestDisplayName, ensureGuestId, storedGuestId } from '../guestIdentity';

describe('isGuestId', () => {
  it('接受合法格式', () => {
    expect(isGuestId('guest_abcdefghij123456')).toBe(true);
    expect(isGuestId(`guest_${'a'.repeat(16)}`)).toBe(true);
  });

  it('拒绝非法格式', () => {
    expect(isGuestId('guest_')).toBe(false);
    expect(isGuestId('abc123')).toBe(false);
    expect(isGuestId(null)).toBe(false);
    expect(isGuestId(undefined)).toBe(false);
    expect(isGuestId('guest_ab!')).toBe(false);
  });
});

describe('guestDisplayName', () => {
  it('格式正确且由 ID 稳定推出', () => {
    const name = guestDisplayName('guest_abc123');
    expect(name).toMatch(/^Learner \d{4}$/);
    expect(guestDisplayName('guest_abc123')).toBe(name);
  });
});

describe('ensureGuestId', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('无存储时生成并持久化（格式 guest_ + 20 位字母数字）', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
    const id = await ensureGuestId();
    expect(isGuestId(id)).toBe(true);
    expect(id).toMatch(/^guest_[A-Za-z0-9]{20}$/);
    expect(AsyncStorage.setItem).toHaveBeenCalledWith('learningSystem.guestId', id);
  });

  it('已有合法 ID 时不重新生成', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue('guest_existingabcdefgh');
    const id = await ensureGuestId();
    expect(id).toBe('guest_existingabcdefgh');
    expect(AsyncStorage.setItem).not.toHaveBeenCalled();
  });

  it('存储读不出来时不覆盖原 ID，请求头仍能拿到同一个临时 ID', async () => {
    (AsyncStorage.getItem as jest.Mock).mockRejectedValue(new Error('storage unavailable'));
    const id = await ensureGuestId();
    expect(isGuestId(id)).toBe(true);
    expect(AsyncStorage.setItem).not.toHaveBeenCalled();
    // authHeaders 经 storedGuestId 取 ID：存储照样读不出来，要退回同一个临时 ID，而不是 null
    expect(await storedGuestId()).toBe(id);
    // 同一次启动里再要一次，还是它
    expect(await ensureGuestId()).toBe(id);
  });
});
