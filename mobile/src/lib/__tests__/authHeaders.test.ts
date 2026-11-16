/* eslint-disable import/first -- jest.mock 必须在 import 之前 */
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
jest.mock('../guestIdentity', () => ({
  storedGuestId: jest.fn(() => Promise.resolve(null)),
}));

import * as SecureStore from 'expo-secure-store';
import { getAuthHeaders } from '../authHeaders';
import { storedGuestId } from '../guestIdentity';

describe('getAuthHeaders', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('有 token 时带 X-Session-Token', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue('token123');
    await expect(getAuthHeaders()).resolves.toEqual({ 'X-Session-Token': 'token123' });
  });

  it('无 token 有 guest id 时带 X-Guest-Id', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
    (storedGuestId as jest.Mock).mockResolvedValue('guest_abc123');
    await expect(getAuthHeaders()).resolves.toEqual({ 'X-Guest-Id': 'guest_abc123' });
  });

  it('两者都没有时为空对象', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
    (storedGuestId as jest.Mock).mockResolvedValue(null);
    await expect(getAuthHeaders()).resolves.toEqual({});
  });

  it('token 优先于 guest id', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue('token123');
    (storedGuestId as jest.Mock).mockResolvedValue('guest_abc123');
    await expect(getAuthHeaders()).resolves.toEqual({ 'X-Session-Token': 'token123' });
  });
});
