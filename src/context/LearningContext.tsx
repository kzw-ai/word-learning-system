import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  fetchUsers,
  getApiBaseUrl,
  getDefaultApiBaseUrl,
  setApiBaseUrlOverride
} from '@/src/lib/apiClient';
import type { UserProfileSummary } from '@/src/lib/types';
import { ensureGuestId, hasStoredGuestId, safeGetItem, safeRemoveItem, safeSetItem } from '@/src/lib/guestIdentity';
import { buildApiUrl } from '@/src/lib/apiClient';

// 开发期才允许用 UserSwitcher 切换到任意测试用户（后端也须设 ALLOW_USER_ID_PARAM=1）
const IS_DEV = process.env.NODE_ENV !== 'production';

export interface LearningUser {
  userId: string;
  username?: string | null;
  languageLevel?: string | null;
  nativeLanguage?: string | null;
  lastStudied?: string | null;
  wordsStudied?: number;
  lastSession?: {
    wordId?: number | null;
    word?: string | null;
    moduleType?: string | null;
    sessionType?: string | null;
    startedAt?: string | null;
  };
}

/* eslint-disable @typescript-eslint/no-unused-vars, no-unused-vars */
interface LearningContextValue {
  userId: string;
  setUserId: (_value: string) => void;
  availableUsers: LearningUser[];
  apiBaseUrl: string;
  setApiBaseUrl: (_value: string) => void;
  resetApiBaseUrl(): void;
  usersLoading: boolean;
  refreshUsers(): Promise<void>;
}
/* eslint-enable @typescript-eslint/no-unused-vars, no-unused-vars */

const DEFAULT_USERS: LearningUser[] = [
  { userId: 'test_user_001' },
  { userId: 'test_user_002' },
  { userId: 'test_user_003' },
  { userId: 'user123' }
];

const USER_STORAGE_KEY = 'learningSystem.userId';
const USERS_STORAGE_KEY = 'learningSystem.availableUsers';

const LearningContext = createContext<LearningContextValue | undefined>(undefined);

/**
 * 当前身份：登录账号 > 开发期手动切换的测试用户 > 本设备的访客 ID。
 * 访客 ID 总是先确保存在，它的 cookie 是后端识别未登录访客的依据。
 */
const LOGIN_KEYS = ['session_token', 'user_id', 'username'];

const writeSessionCookie = (token: string) => {
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `session_token=${token}; Path=/; Max-Age=604800; SameSite=Lax${secure}`;
};

/**
 * 这台浏览器第一次拿到访客 ID 时，把它原先以 test_user_001（或开发期选过的
 * 测试用户）身份存在本地的学习位置挪过来，免得部署后老访客的续学进度丢失。
 * 只动本地存储；共享测试账号在数据库里的记录不搬，那不属于这个访客。
 */
const migrateLegacyLocalSession = (guestId: string) => {
  const legacyId = safeGetItem(USER_STORAGE_KEY) || DEFAULT_USERS[0].userId;
  const legacy = safeGetItem(`learningSession:${legacyId}`);
  if (legacy && !safeGetItem(`learningSession:${guestId}`)) {
    safeSetItem(`learningSession:${guestId}`, legacy);
  }
};

const readInitialUserId = () => {
  const isFirstGuestVisit = !hasStoredGuestId();
  const guestId = ensureGuestId();
  const token = safeGetItem('session_token');
  const accountId = safeGetItem('user_id');
  if (token && accountId) {
    // 页面里很多请求是不带认证头的普通 fetch，后端靠 cookie 认人。登录时下发的
    // cookie 是会话级的，浏览器重开后就没了，而 localStorage 里的凭证还在——
    // 此时请求会被当成访客、与账号对不上而被拒。这里同步补写一份；若服务器的
    // HttpOnly cookie 仍在，浏览器会忽略这次写入
    writeSessionCookie(token);
    return accountId;
  }
  if (IS_DEV) {
    const stored = safeGetItem(USER_STORAGE_KEY);
    if (stored) return stored;
  }
  if (isFirstGuestVisit) {
    migrateLegacyLocalSession(guestId);
  }
  return guestId;
};

const readInitialUsers = (): LearningUser[] => {
  if (typeof window === 'undefined') {
    return DEFAULT_USERS;
  }
  const stored = safeGetItem(USERS_STORAGE_KEY);
  if (!stored) {
    return DEFAULT_USERS;
  }
  try {
    const parsed = JSON.parse(stored) as LearningUser[];
    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed.filter(user => typeof user === 'object' && user !== null && 'userId' in user);
    }
  } catch (error) {
    console.warn('Failed to parse stored users list', error);
  }
  return DEFAULT_USERS;
};

const normalizeProfile = (profile: UserProfileSummary): LearningUser => ({
  userId: profile.userId,
  username: profile.username ?? null,
  languageLevel: profile.languageLevel ?? null,
  nativeLanguage: profile.nativeLanguage ?? null,
  lastStudied: profile.lastStudied ?? null,
  wordsStudied: typeof profile.wordsStudied === 'number' ? profile.wordsStudied : 0,
  lastSession: profile.lastSession
});

const mergeUser = (base: LearningUser | undefined, incoming: LearningUser): LearningUser => ({
  userId: incoming.userId,
  username: incoming.username ?? base?.username ?? null,
  languageLevel: incoming.languageLevel ?? base?.languageLevel ?? null,
  nativeLanguage: incoming.nativeLanguage ?? base?.nativeLanguage ?? null,
  lastStudied: incoming.lastStudied ?? base?.lastStudied ?? null,
  wordsStudied:
    typeof incoming.wordsStudied === 'number'
      ? incoming.wordsStudied
      : base?.wordsStudied ?? 0,
  lastSession: incoming.lastSession ?? base?.lastSession
});

const sortUsers = (users: LearningUser[]) =>
  users.slice().sort((a, b) => a.userId.localeCompare(b.userId));

export const LearningProvider: React.FC<React.PropsWithChildren<{}>> = ({ children }) => {
  // 初始值必须与 SSR 一致（不读 localStorage），挂载后由下方 effect 加载存储值，
  // 否则老用户回访时首次客户端渲染与预渲染 HTML 不一致，触发水合错误
  // 首帧为空：真实身份要到挂载后才能从 localStorage 读出。各处据此先不发请求，
  // 否则会先以一个不属于自己的 ID 请求一轮（现在会被后端拒绝）
  const [userId, setUserIdState] = useState<string>('');
  const [availableUsers, setAvailableUsers] = useState<LearningUser[]>(DEFAULT_USERS);
  const [apiBaseUrl, setApiBaseUrlState] = useState<string>(() => getDefaultApiBaseUrl());
  const [usersLoading, setUsersLoading] = useState(false);

  useEffect(() => {
    setUserIdState(readInitialUserId());

    const token = safeGetItem('session_token');
    if (token) {
      // 本地存着的登录凭证可能已过期：校验一次，失效就清掉，退回访客身份
      fetch(buildApiUrl('/api/auth/validate'), { headers: { 'X-Session-Token': token } })
        .then(r => r.json())
        .then(result => {
          // 响应较慢时用户可能已重新登录：只处理被校验的那个凭证，
          // 否则旧凭证的「失效」会把刚登录的新账号清掉
          if (result && result.valid === false && safeGetItem('session_token') === token) {
            LOGIN_KEYS.forEach(safeRemoveItem);
            document.cookie = 'session_token=; Path=/; Max-Age=0';
            setUserIdState(ensureGuestId());
          }
        })
        .catch(() => {
          // 网络失败时保持现状，不因为一次失败就登出
        });
    } else {
      // 本地没有凭证，但服务器下发的 HttpOnly 登录 cookie 可能还有效（JS 读不到它）。
      // 后端会按这个 cookie 认人，前端若仍当自己是访客，请求就会对不上而被拒
      fetch(buildApiUrl('/api/auth/validate'))
        .then(r => r.json())
        .then(result => {
          if (result && result.valid && result.user_id && !safeGetItem('session_token')) {
            setUserIdState(result.user_id);
          }
        })
        .catch(() => {
          // 拿不到就按访客继续
        });
    }
    setAvailableUsers(readInitialUsers());
    setApiBaseUrlState(getApiBaseUrl());
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    setApiBaseUrlOverride(apiBaseUrl);
  }, [apiBaseUrl]);

  const persistUsers = useCallback((users: LearningUser[]) => {
    if (typeof window === 'undefined') {
      return;
    }
    safeSetItem(USERS_STORAGE_KEY, JSON.stringify(users));
  }, []);

  const updateAvailableUsers = useCallback((nextUser: LearningUser) => {
    if (!nextUser.userId) {
      return;
    }
    setAvailableUsers(prev => {
      const map = new Map<string, LearningUser>();
      prev.forEach(user => {
        map.set(user.userId, user);
      });
      const existing = map.get(nextUser.userId);
      map.set(nextUser.userId, mergeUser(existing, nextUser));
      const next = sortUsers(Array.from(map.values()));
      persistUsers(next);
      return next;
    });
  }, [persistUsers]);

  const setUserId = useCallback((nextUserId: string) => {
    const trimmed = nextUserId.trim();
    if (!trimmed) {
      return;
    }
    setUserIdState(trimmed);
    updateAvailableUsers({ userId: trimmed });
    if (typeof window !== 'undefined') {
      safeSetItem(USER_STORAGE_KEY, trimmed);
    }
  }, [updateAvailableUsers]);

  const setApiBaseUrl = useCallback((url: string) => {
    const trimmed = url.trim();
    if (!trimmed) {
      setApiBaseUrlState(getDefaultApiBaseUrl());
      setApiBaseUrlOverride(null);
      return;
    }
    setApiBaseUrlState(trimmed.replace(/\/$/, ''));
  }, []);

  const resetApiBaseUrl = useCallback(() => {
    setApiBaseUrlState(getDefaultApiBaseUrl());
    setApiBaseUrlOverride(null);
  }, []);

  const refreshUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const remote = await fetchUsers({ limit: 200 }).catch(() => [] as UserProfileSummary[]);
      if (Array.isArray(remote) && remote.length > 0) {
        const normalized = remote.map(normalizeProfile);
        setAvailableUsers(prev => {
          const map = new Map<string, LearningUser>();
          prev.forEach(user => {
            map.set(user.userId, user);
          });
          normalized.forEach(user => {
            const existing = map.get(user.userId);
            map.set(user.userId, mergeUser(existing, user));
          });
          const next = sortUsers(Array.from(map.values()));
          persistUsers(next);
          return next;
        });
      } else {
        // 确保默认用户依然可用
        setAvailableUsers(prev => {
          if (prev.length === 0) {
            persistUsers(DEFAULT_USERS);
            return DEFAULT_USERS;
          }
          return prev;
        });
      }
    } catch (error) {
      console.warn('Failed to fetch users', error);
    } finally {
      setUsersLoading(false);
    }
  }, [persistUsers]);

  useEffect(() => {
    // 用户列表只供开发期的 UserSwitcher 使用，生产环境后端不提供
    if (IS_DEV) refreshUsers();
  }, [refreshUsers, apiBaseUrl]);

  const value = useMemo<LearningContextValue>(() => ({
    userId,
    setUserId,
    availableUsers,
    apiBaseUrl,
    setApiBaseUrl,
    resetApiBaseUrl,
    usersLoading,
    refreshUsers
  }), [apiBaseUrl, availableUsers, resetApiBaseUrl, setApiBaseUrl, setUserId, userId, usersLoading, refreshUsers]);

  return (
    <LearningContext.Provider value={value}>
      {children}
    </LearningContext.Provider>
  );
};

export const useLearningContext = () => {
  const context = useContext(LearningContext);
  if (!context) {
    throw new Error('useLearningContext must be used within LearningProvider');
  }
  return context;
};
