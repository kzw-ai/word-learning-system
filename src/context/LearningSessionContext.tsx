import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useLearningContext } from '@/src/context/LearningContext';
import { fetchLearningState, saveLearningState } from '@/src/lib/apiClient';

export interface LearningSessionState {
  wordId?: number | null;
  word?: string | null;
  module?: string | null;
  vksLevel?: string | null;
  lastUpdated?: string | null;
}

/* eslint-disable @typescript-eslint/no-unused-vars, no-unused-vars */
interface LearningSessionContextValue {
  session: LearningSessionState;
  /**
   * localStorage 是否已读入。首帧为 false（SSR 一致性要求），挂载后置 true。
   * 追踪器要等它变 true 再创建，否则会先带着空 vksLevel 建一次会话。
   */
  hydrated: boolean;
  updateSession(session: Partial<LearningSessionState>): void;
  clearSession(): void;
}
/* eslint-enable @typescript-eslint/no-unused-vars, no-unused-vars */

const DEFAULT_SESSION: LearningSessionState = {
  wordId: null,
  word: null,
  module: null,
  vksLevel: null,
  lastUpdated: null
};

const LearningSessionContext = createContext<LearningSessionContextValue | undefined>(undefined);

const storageKeyForUser = (userId: string) => `learningSession:${userId}`;

const loadSessionFromStorage = (userId: string): LearningSessionState => {
  if (typeof window === 'undefined') {
    return DEFAULT_SESSION;
  }
  try {
    const raw = window.localStorage.getItem(storageKeyForUser(userId));
    if (!raw) {
      return DEFAULT_SESSION;
    }
    const parsed = JSON.parse(raw) as LearningSessionState;
    if (parsed && typeof parsed === 'object') {
      return {
        wordId: parsed.wordId ?? null,
        word: parsed.word ?? null,
        module: parsed.module ?? null,
        vksLevel: parsed.vksLevel ?? null,
        lastUpdated: parsed.lastUpdated ?? null
      };
    }
  } catch (error) {
    console.warn('Failed to parse learning session from storage', error);
  }
  return DEFAULT_SESSION;
};

const persistSessionToStorage = (userId: string, session: LearningSessionState) => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(storageKeyForUser(userId), JSON.stringify(session));
  } catch (error) {
    console.warn('Failed to persist learning session', error);
  }
};

/** Debounce timer ref type */
type TimerRef = ReturnType<typeof setTimeout> | null;

export const LearningSessionProvider: React.FC<React.PropsWithChildren<{}>> = ({ children }) => {
  const { userId } = useLearningContext();
  // 初始值必须与 SSR 一致（不读 localStorage），挂载后由下方 effect 加载存储值，
  // 否则老用户带着存储的会话回访时会触发 React 水合错误
  const [session, setSession] = useState<LearningSessionState>(DEFAULT_SESSION);
  const [hydrated, setHydrated] = useState(false);
  const saveTimerRef = useRef<TimerRef>(null);
  const userIdRef = useRef(userId);

  // Keep userIdRef in sync
  useEffect(() => {
    userIdRef.current = userId;
  }, [userId]);

  // Load from localStorage on user switch, then async-fetch from backend
  useEffect(() => {
    const localSession = loadSessionFromStorage(userId);
    setSession(localSession);
    setHydrated(true);

    // Async: fetch from backend and use if newer
    fetchLearningState(userId)
      .then(serverState => {
        if (!serverState || (!serverState.wordId && !serverState.module)) {
          return; // Server has no data, keep local
        }

        const serverTime = serverState.lastUpdated ? new Date(serverState.lastUpdated).getTime() : 0;
        const localTime = localSession.lastUpdated ? new Date(localSession.lastUpdated).getTime() : 0;

        if (serverTime > localTime) {
          // Server data is newer, use it
          const merged: LearningSessionState = {
            wordId: serverState.wordId ?? localSession.wordId,
            word: serverState.word ?? localSession.word,
            module: serverState.module ?? localSession.module,
            vksLevel: serverState.vksLevel ?? localSession.vksLevel,
            lastUpdated: serverState.lastUpdated ?? localSession.lastUpdated
          };
          setSession(merged);
          persistSessionToStorage(userId, merged);
          console.log('📥 学习进度已从服务器恢复');
        }
      })
      .catch(err => {
        console.warn('Failed to fetch learning state from server:', err);
      });
  }, [userId]);

  // Debounced save to backend
  const syncToBackend = useCallback((state: LearningSessionState) => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(() => {
      const uid = userIdRef.current;
      saveLearningState(uid, {
        wordId: state.wordId,
        word: state.word,
        module: state.module,
        vksLevel: state.vksLevel
      }).then(() => {
        console.log('📤 学习进度已同步到服务器');
      }).catch(err => {
        console.warn('Failed to save learning state to server:', err);
      });
    }, 1000); // Debounce 1 second
  }, []);

  const updateSession = useCallback((partial: Partial<LearningSessionState>) => {
    setSession(prev => {
      const timestamp = partial.lastUpdated ?? new Date().toISOString();
      // 丢掉值为 undefined 的键：展开运算符会让显式的 undefined 覆盖掉已有值，
      // 复习/推荐入口传 { vksLevel: undefined } 时会把用户的 VKS 自评抹成 null，
      // 学习会话的 initial_level 于是又全写成 NULL。要清空请显式传 null。
      const defined = Object.fromEntries(
        Object.entries(partial).filter(([, value]) => value !== undefined)
      ) as Partial<LearningSessionState>;
      // VKS 是对「某个词」的自评。换到另一个词却没给新自评时（推荐/复习入口），
      // 不能沿用上一个词的档位，否则新词的 initial_level 会记成旧词的。
      if (
        defined.wordId !== undefined &&
        defined.wordId !== prev.wordId &&
        defined.vksLevel === undefined
      ) {
        defined.vksLevel = null;
      }
      const next: LearningSessionState = {
        ...prev,
        ...defined,
        lastUpdated: timestamp
      };
      persistSessionToStorage(userIdRef.current, next);
      syncToBackend(next);
      return next;
    });
  }, [syncToBackend]);

  const clearSession = useCallback(() => {
    setSession(DEFAULT_SESSION);
    persistSessionToStorage(userId, DEFAULT_SESSION);
    // Also clear on server
    saveLearningState(userId, {
      wordId: null,
      word: null,
      module: null,
      vksLevel: null
    }).catch(err => {
      console.warn('Failed to clear learning state on server:', err);
    });
  }, [userId]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  const value = useMemo<LearningSessionContextValue>(() => ({
    session,
    hydrated,
    updateSession,
    clearSession
  }), [session, hydrated, updateSession, clearSession]);

  return (
    <LearningSessionContext.Provider value={value}>
      {children}
    </LearningSessionContext.Provider>
  );
};

export const useLearningSession = () => {
  const context = useContext(LearningSessionContext);
  if (!context) {
    throw new Error('useLearningSession must be used within LearningSessionProvider');
  }
  return context;
};
