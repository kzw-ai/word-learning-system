// 源文件：src/context/LearningContext.tsx（网页版）。RN 版：凭证用 SecureStore，
// guest id 用 AsyncStorage；去掉 UserSwitcher / 开发期测试用户（App 不需要）。
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { ensureGuestId } from '@/lib/guestIdentity';
import { getSecure, removeSecure, AUTH_KEYS } from '@/lib/storage';
import { getDefaultApiBaseUrl, setApiBaseUrl as setApiBaseUrlOverride } from '@/lib/apiClient';
import { authenticatedFetch } from '@/lib/authClient';

interface LearningContextValue {
  /** 当前身份：登录账号 id，或未登录访客的 guest id。首帧为空（异步读存储）。 */
  userId: string;
  setUserId: (id: string) => void;
  apiBaseUrl: string;
  setApiBaseUrl: (url: string) => void;
  resetApiBaseUrl: () => void;
}

const LearningContext = createContext<LearningContextValue | undefined>(undefined);

export const LearningProvider: React.FC<React.PropsWithChildren<{}>> = ({ children }) => {
  const [userId, setUserIdState] = useState<string>('');
  const [apiBaseUrl, setApiBaseUrlState] = useState<string>(getDefaultApiBaseUrl());

  useEffect(() => {
    // 启动时确定身份：登录账号（SecureStore 有 token + user_id）> 访客（生成/读 guest id）。
    (async () => {
      const token = await getSecure('session_token');
      const accountId = await getSecure('user_id');
      if (token && accountId) {
        setUserIdState(accountId);
        // 本地存的登录凭证可能已过期：校验一次，失效就清掉退回访客身份。
        try {
          const resp = await authenticatedFetch('/api/auth/validate');
          const result = await resp.json();
          if (result && result.valid === false) {
            for (const key of AUTH_KEYS) await removeSecure(key);
            setUserIdState(await ensureGuestId());
          }
        } catch {
          // 网络失败时保持现状，不因为一次失败就登出
        }
      } else {
        setUserIdState(await ensureGuestId());
      }
    })();
  }, []);

  const setUserId = useCallback((id: string) => {
    const trimmed = id.trim();
    if (!trimmed) return;
    setUserIdState(trimmed);
  }, []);

  const setApiBaseUrl = useCallback((url: string) => {
    const trimmed = url.trim();
    if (!trimmed) {
      setApiBaseUrlState(getDefaultApiBaseUrl());
      setApiBaseUrlOverride(null);
      return;
    }
    const normalized = trimmed.replace(/\/$/, '');
    setApiBaseUrlState(normalized);
    setApiBaseUrlOverride(normalized);
  }, []);

  const resetApiBaseUrl = useCallback(() => {
    setApiBaseUrlState(getDefaultApiBaseUrl());
    setApiBaseUrlOverride(null);
  }, []);

  const value = useMemo<LearningContextValue>(() => ({
    userId,
    setUserId,
    apiBaseUrl,
    setApiBaseUrl,
    resetApiBaseUrl,
  }), [userId, setUserId, apiBaseUrl, setApiBaseUrl, resetApiBaseUrl]);

  return <LearningContext.Provider value={value}>{children}</LearningContext.Provider>;
};

export const useLearningContext = () => {
  const context = useContext(LearningContext);
  if (!context) {
    throw new Error('useLearningContext must be used within LearningProvider');
  }
  return context;
};
