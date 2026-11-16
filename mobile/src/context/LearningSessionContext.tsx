// 源文件：src/context/LearningSessionContext.tsx（网页版）。RN 版：localStorage → AsyncStorage。
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useLearningContext } from './LearningContext';
import { fetchLearningState, saveLearningState } from '@/lib/apiClient';
import { getLocal, setLocal } from '@/lib/storage';

export interface LearningSessionState {
  wordId?: number | null;
  word?: string | null;
  module?: string | null;
  vksLevel?: string | null;
  /** 从「今日复习」进入时为 true：学完一个词后回到复习列表继续下一个，只存本地。 */
  reviewMode?: boolean | null;
  /** 今天已经复习过的词（当天有效），只存本地。 */
  reviewedWordIds?: number[] | null;
  reviewDate?: string | null;
  /** 这一轮从哪一步进入（VKS 自评或复习推荐决定），只存本地。 */
  entryModule?: string | null;
  /** 照哪条推荐开始学这个词（adaptive_recommendation.id）。 */
  recommendationId?: number | null;
  lastUpdated?: string | null;
}

interface LearningSessionContextValue {
  session: LearningSessionState;
  /** 本地状态是否已读入（首帧 false，读完后 true）。追踪器等它就绪才建会话。 */
  hydrated: boolean;
  /** 服务器上的学习状态是否已恢复完（取回、失败或超时）。 */
  restored: boolean;
  /** 服务器状态确实取回了（不含超时与失败）。 */
  serverStateLoaded: boolean;
  updateSession: (session: Partial<LearningSessionState>) => void;
  clearSession: () => void;
}

const DEFAULT_SESSION: LearningSessionState = {
  wordId: null,
  word: null,
  module: null,
  vksLevel: null,
  reviewMode: null,
  reviewedWordIds: null,
  reviewDate: null,
  entryModule: null,
  recommendationId: null,
  lastUpdated: null,
};

const LearningSessionContext = createContext<LearningSessionContextValue | undefined>(undefined);

const storageKeyForUser = (userId: string) => `learningSession:${userId}`;

const loadSessionFromStorage = async (userId: string): Promise<LearningSessionState> => {
  try {
    const raw = await getLocal(storageKeyForUser(userId));
    if (!raw) return DEFAULT_SESSION;
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
        recommendationId: typeof parsed.recommendationId === 'number' ? parsed.recommendationId : null,
        lastUpdated: parsed.lastUpdated ?? null,
      };
    }
  } catch (error) {
    console.warn('Failed to parse learning session from storage', error);
  }
  return DEFAULT_SESSION;
};

const persistSessionToStorage = async (userId: string, session: LearningSessionState) => {
  try {
    await setLocal(storageKeyForUser(userId), JSON.stringify(session));
  } catch (error) {
    console.warn('Failed to persist learning session', error);
  }
};

export const LearningSessionProvider: React.FC<React.PropsWithChildren<{}>> = ({ children }) => {
  const { userId } = useLearningContext();
  const [session, setSession] = useState<LearningSessionState>(DEFAULT_SESSION);
  const [hydrated, setHydrated] = useState(false);
  const [restoredFor, setRestoredFor] = useState<string | null>(null);
  const restored = Boolean(userId) && restoredFor === userId;
  const [serverStateFor, setServerStateFor] = useState<string | null>(null);
  const serverStateLoaded = Boolean(userId) && serverStateFor === userId;
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveChainRef = useRef<Promise<void>>(Promise.resolve());
  const userIdRef = useRef(userId);

  useEffect(() => {
    userIdRef.current = userId;
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  }, [userId]);

  // 身份确定后：先读本地，再从服务器取回（较新的覆盖本地），3 秒超时兜底。
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    (async () => {
      const localSession = await loadSessionFromStorage(userId);
      if (cancelled) return;
      setSession(localSession);
      setHydrated(true);

      let finished = false;
      const finishRestore = () => {
        if (finished || userIdRef.current !== userId) return;
        finished = true;
        setRestoredFor(userId);
      };
      const restoreTimer = setTimeout(finishRestore, 3000);

      try {
        const serverState = await fetchLearningState(userId);
        if (cancelled || userIdRef.current !== userId) return;
        setServerStateFor(userId);
        if (!serverState || (!serverState.wordId && !serverState.module)) return;
        const serverTime = serverState.lastUpdated ? new Date(serverState.lastUpdated).getTime() : 0;
        setSession(prev => {
          const localTime = prev.lastUpdated ? new Date(prev.lastUpdated).getTime() : 0;
          if (serverTime <= localTime) return prev;
          const wordId = serverState.wordId ?? prev.wordId;
          const sameWord = wordId === prev.wordId;
          const merged: LearningSessionState = {
            ...prev,
            wordId,
            word: serverState.word ?? prev.word,
            module: serverState.module ?? prev.module,
            vksLevel: serverState.vksLevel ?? (sameWord ? prev.vksLevel : null),
            recommendationId: serverState.recommendationId ?? null,
            reviewMode: sameWord ? prev.reviewMode : null,
            lastUpdated: serverState.lastUpdated ?? prev.lastUpdated,
          };
          persistSessionToStorage(userId, merged);
          return merged;
        });
      } catch (error) {
        console.warn('Failed to fetch learning state from server:', error);
      } finally {
        clearTimeout(restoreTimer);
        finishRestore();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const syncToBackend = useCallback((state: LearningSessionState) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    const uid = userIdRef.current;
    if (!uid) return;
    saveTimerRef.current = setTimeout(() => {
      saveChainRef.current = saveChainRef.current.then(() =>
        saveLearningState(uid, {
          wordId: state.wordId,
          word: state.word,
          module: state.module,
          vksLevel: state.vksLevel,
          recommendationId: state.recommendationId ?? null,
        })
      ).catch(error => console.warn('Failed to save learning state to server:', error));
    }, 1000);
  }, []);

  const updateSession = useCallback((partial: Partial<LearningSessionState>) => {
    setSession(prev => {
      const timestamp = partial.lastUpdated ?? new Date().toISOString();
      const defined = Object.fromEntries(
        Object.entries(partial).filter(([, value]) => value !== undefined)
      ) as Partial<LearningSessionState>;
      // VKS / 推荐都是针对「某个词」的：换词却没给新值时不沿用上一个词的。
      if (defined.wordId !== undefined && defined.wordId !== prev.wordId && defined.vksLevel === undefined) {
        defined.vksLevel = null;
      }
      if (defined.wordId !== undefined && defined.wordId !== prev.wordId && defined.recommendationId === undefined) {
        defined.recommendationId = null;
      }
      const unchanged = partial.lastUpdated === undefined && Object.entries(defined).every(
        ([key, value]) => JSON.stringify(value) === JSON.stringify(prev[key as keyof LearningSessionState] ?? null)
      );
      if (unchanged) return prev;
      const next: LearningSessionState = { ...prev, ...defined, lastUpdated: timestamp };
      if (userIdRef.current) {
        persistSessionToStorage(userIdRef.current, next);
        syncToBackend(next);
      }
      return next;
    });
  }, [syncToBackend]);

  const clearSession = useCallback(() => {
    setSession(DEFAULT_SESSION);
    persistSessionToStorage(userId, DEFAULT_SESSION);
    saveChainRef.current = saveChainRef.current.then(() =>
      saveLearningState(userId, {
        wordId: null,
        word: null,
        module: null,
        vksLevel: null,
        recommendationId: null,
      })
    ).catch(() => {});
  }, [userId]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  const value = useMemo<LearningSessionContextValue>(() => ({
    session,
    hydrated,
    restored,
    serverStateLoaded,
    updateSession,
    clearSession,
  }), [session, hydrated, restored, serverStateLoaded, updateSession, clearSession]);

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
