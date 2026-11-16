/* eslint-disable import/first -- jest.mock 必须在 import 之前 */
jest.mock('expo-crypto', () => ({
  getRandomValues: (arr: Uint8Array) => arr,
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

import { buildApiUrl, setApiBaseUrl, getApiBaseUrl, resolveDefaultBase } from '../apiClient';

describe('buildApiUrl', () => {
  it('拼接相对路径（带 / 与不带 /）', () => {
    setApiBaseUrl('http://127.0.0.1:5014');
    expect(buildApiUrl('/word/1')).toBe('http://127.0.0.1:5014/word/1');
    expect(buildApiUrl('word/1')).toBe('http://127.0.0.1:5014/word/1');
  });

  it('绝对 URL 原样透传', () => {
    expect(buildApiUrl('http://example.com/x')).toBe('http://example.com/x');
    expect(buildApiUrl('https://example.com/x')).toBe('https://example.com/x');
  });

  it('base URL 去尾部斜杠', () => {
    setApiBaseUrl('http://127.0.0.1:5014/');
    expect(buildApiUrl('/word/1')).toBe('http://127.0.0.1:5014/word/1');
  });

  it('空路径返回 base URL', () => {
    setApiBaseUrl('http://127.0.0.1:5014');
    expect(buildApiUrl('')).toBe('http://127.0.0.1:5014');
  });

  it('默认 base URL 是本地后端 5014', () => {
    setApiBaseUrl(null);
    expect(getApiBaseUrl()).toBe('http://127.0.0.1:5014');
  });
});

describe('resolveDefaultBase', () => {
  it('开发包默认本地后端', () => {
    expect(resolveDefaultBase(true)).toBe('http://127.0.0.1:5014');
  });

  it('正式包默认线上地址', () => {
    expect(resolveDefaultBase(false)).toBe('https://learnchinese.kzwbelieve.top');
  });

  it('环境变量优先', () => {
    expect(resolveDefaultBase(true, 'http://192.168.1.10:5014')).toBe('http://192.168.1.10:5014');
    expect(resolveDefaultBase(false, 'http://192.168.1.10:5014/')).toBe('http://192.168.1.10:5014');
  });
});
