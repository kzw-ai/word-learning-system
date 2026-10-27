import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useLearningContext } from '@/src/context/LearningContext';
import { fetchLearningState, saveLearningState } from '@/src/lib/apiClient';

export interface LearningSessionState {
  wordId?: number | null;
  word?: string | null;
  module?: string | null;
  vksLevel?: string | null;
  /**
   * 从「今日复习」进入时为 true：学完一个词后回到复习列表继续下一个，
   * 而不是去学习看板。只存本地，不同步到服务器。
   */
  reviewMode?: boolean | null;
  /**
   * 今天已经复习过的词。复习列表据此过滤，不依赖后端把它们移出到期列表——
   * 作答没能记录时（例如未登录、追踪器停用），否则会一直重复同一个词。
   * 只在 reviewDate 当天有效，过了这一天自动失效，不会挡住之后再次到期的词。
   */
  reviewedWordIds?: number[] | null;
  reviewDate?: string | null;
  /**
   * 这一轮从哪一步进入（VKS 自评或复习 / 推荐决定）。步骤进度条据此把之前的
   * 步骤显示为「已跳过」。只存本地。
   */
  entryModule?: string | null;
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
  reviewMode: null,
  reviewedWordIds: null,
  reviewDate: null,
  entryModule: null,
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
        reviewMode: parsed.reviewMode ?? null,
        reviewedWordIds: Array.isArray(parsed.reviewedWordIds) ? parsed.reviewedWordIds : null,
        reviewDate: parsed.reviewDate ?? null,
        entryModule: parsed.entryModule ?? null,
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

        // 请求期间切换了用户：这是上一个用户的数据，丢弃
        if (userIdRef.current !== userId) {
          return;
        }
        const serverTime = serverState.lastUpdated ? new Date(serverState.lastUpdated).getTime() : 0;

        // 与「当前」会话比较，而不是请求发出时的快照：请求较慢时用户可能已经
        // 开始了新的学习或复习，旧响应不能把它覆盖回去
        setSession(prev => {
          const localTime = prev.lastUpdated ? new Date(prev.lastUpdated).getTime() : 0;
          if (serverTime <= localTime) {
            return prev;
          }
          const wordId = serverState.wordId ?? prev.wordId;
          // 复习状态只存本地。服务器上是另一个词时，说明在别处开始了别的学习，
          // 本地的复习模式不再适用
          const sameWord = wordId === prev.wordId;
          const merged: LearningSessionState = {
            ...prev,
            wordId,
            word: serverState.word ?? prev.word,
            module: serverState.module ?? prev.module,
            vksLevel: serverState.vksLevel ?? prev.vksLevel,
            reviewMode: sameWord ? prev.reviewMode : null,
            lastUpdated: serverState.lastUpdated ?? prev.lastUpdated
          };
          persistSessionToStorage(userId, merged);
          console.log('📥 学习进度已从服务器恢复');
          return merged;
        });
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

const localDateKey = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** 今天已复习过的词；记录不是今天的就视为空 */
export const reviewedToday = (session: LearningSessionState): number[] =>
  session.reviewDate === localDateKey() ? session.reviewedWordIds ?? [] : [];

export const todayReviewKey = localDateKey;

/** 学完一个词之后去哪：复习模式回到复习列表，否则去学习看板 */
export const afterWordRoute = (session: LearningSessionState) =>
  session.reviewMode ? '/today-review' : '/learning-dashboard';

export const useLearningSession = () => {
  const context = useContext(LearningSessionContext);
  if (!context) {
    throw new Error('useLearningSession must be used within LearningSessionProvider');
  }
  return context;
};
