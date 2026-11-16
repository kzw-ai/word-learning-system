// 存储封装：敏感凭证用 SecureStore（iOS Keychain / Android Keystore），
// 非敏感本地状态用 AsyncStorage（卸载即清，guest id 重装后重新生成）。
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

// —— 敏感凭证（session token、user_id、username）——
export const getSecure = (key: string): Promise<string | null> =>
  SecureStore.getItemAsync(key).catch(() => null);

export const setSecure = (key: string, value: string): Promise<void> =>
  SecureStore.setItemAsync(key, value).then(() => undefined).catch(() => undefined);

export const removeSecure = (key: string): Promise<void> =>
  SecureStore.deleteItemAsync(key).then(() => undefined).catch(() => undefined);

// —— 非敏感本地状态（guest id、学习位置本地镜像、界面偏好等）——
export const getLocal = (key: string): Promise<string | null> =>
  AsyncStorage.getItem(key).catch(() => null);

export const setLocal = (key: string, value: string): Promise<void> =>
  AsyncStorage.setItem(key, value).then(() => undefined).catch(() => undefined);

export const removeLocal = (key: string): Promise<void> =>
  AsyncStorage.removeItem(key).then(() => undefined).catch(() => undefined);

/** 登录凭证的键（登录/登出/校验失效时统一读写） */
export const AUTH_KEYS = ['session_token', 'user_id', 'username'] as const;
