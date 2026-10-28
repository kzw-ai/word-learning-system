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
  /**
   * 照哪条推荐开始学这个词（adaptive_recommendation.id）。学习会话带上它，后端据此
   * 算推荐效果。换到另一个词却没给新值时清空，与 vksLevel 同一规则。
   */
  recommendationId?: number | null;
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
  /**
   * 服务器上的学习状态是否已恢复完（取回、失败或超时）。学习页的追踪器等它再建会话：
   * 会话要绑定的 VKS 档位与推荐（recommendationId）可能来自另一台设备，
   * 先建就会带着本地那份可能过时的值。
   * 已知限制：服务器 3 秒仍未响应时按本地值建会话，之后到达的推荐归属不再改已建的会话
   * （档位会由 setInitialLevel 补写）；只影响推荐效果的统计归属。
   */
  restored: boolean;
  /** 服务器上的学习状态确实取回了（不含超时与请求失败）。判断「是不是新用户」要用它 */
  serverStateLoaded: boolean;
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
  recommendationId: null,
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
        recommendationId: typeof parsed.recommendationId === 'number' ? parsed.recommendationId : null,
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
  // 记「为哪个身份恢复完」而不是一个布尔：身份切换的那次渲染里它立刻就不成立。
  // 子组件（学习页追踪器）的 effect 先于这里的 effect 执行，用布尔的话，新身份
  // 的追踪器会读到上一个身份留下的 true
  const [restoredFor, setRestoredFor] = useState<string | null>(null);
  const restored = Boolean(userId) && restoredFor === userId;
  const [serverStateFor, setServerStateFor] = useState<string | null>(null);
  const serverStateLoaded = Boolean(userId) && serverStateFor === userId;
  const saveTimerRef = useRef<TimerRef>(null);
  // 学习状态的 PUT 逐个发：已发出的旧请求晚到时不能覆盖之后的新状态
  const saveChainRef = useRef<Promise<void>>(Promise.resolve());
  const userIdRef = useRef(userId);

  // Keep userIdRef in sync
  useEffect(() => {
    userIdRef.current = userId;
    // 切换身份（登录、开发期换测试用户）时，丢弃上一个身份尚未发出的保存
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  }, [userId]);

  // Load from localStorage on user switch, then async-fetch from backend
  useEffect(() => {
    // 身份尚未确定（首帧）时不加载；hydrated 保持 false，追踪器等它就绪才创建
    if (!userId) return;
    const localSession = loadSessionFromStorage(userId);
    setSession(localSession);
    setHydrated(true);

    // 服务器状态取回、失败或 3 秒仍无响应，都算恢复完：不能让追踪一直等下去
    let finished = false;
    const finishRestore = () => {
      if (finished || userIdRef.current !== userId) return;
      finished = true;
      setRestoredFor(userId);
    };
    const restoreTimer = setTimeout(finishRestore, 3000);

    // Async: fetch from backend and use if newer
    fetchLearningState(userId)
      .then(serverState => {
        if (userIdRef.current === userId) {
          setServerStateFor(userId);
        }
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
            // VKS 是对某个词的自评：服务器上是另一个词时不能沿用本地这个词的档位，
            // 否则新词的会话会把旧词的档位记成 initial_level（与 updateSession 的规则一致）
            vksLevel: serverState.vksLevel ?? (sameWord ? prev.vksLevel : null),
            // 推荐归属随学习位置同步：服务器较新时以它为准（另一台设备可能已从今日复习
            // 重新开始这个词，同一个词也不等于同一轮推荐）
            recommendationId: serverState.recommendationId ?? null,
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
      })
      .finally(() => {
        clearTimeout(restoreTimer);
        finishRestore();
      });
    return () => {
      clearTimeout(restoreTimer);
      finished = true;
    };
  }, [userId]);

  // Debounced save to backend
  const syncToBackend = useCallback((state: LearningSessionState) => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    // 入队时就定下身份：若等到触发时再读，1 秒内切换了身份，旧身份的学习位置
    // 就会写到新身份名下
    const uid = userIdRef.current;
    if (!uid) return;
    saveTimerRef.current = setTimeout(() => {
      saveChainRef.current = saveChainRef.current.then(() => saveLearningState(uid, {
        wordId: state.wordId,
        word: state.word,
        module: state.module,
        vksLevel: state.vksLevel,
        recommendationId: state.recommendationId ?? null
      })).then(() => {
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
      // 推荐也是针对某个词的：换词却没说是照哪条推荐时，不再算照原推荐在学
      if (
        defined.wordId !== undefined &&
        defined.wordId !== prev.wordId &&
        defined.recommendationId === undefined
      ) {
        defined.recommendationId = null;
      }
      // 什么都没变（页面加载时写回同一个词、同一个模块）就什么也不做：刷新时间戳会让
      // 稍后返回的、另一台设备上更新的服务器状态被当成旧的丢掉，还多发一次同步
      const unchanged = partial.lastUpdated === undefined && Object.entries(defined).every(
        ([key, value]) => JSON.stringify(value) === JSON.stringify(prev[key as keyof LearningSessionState] ?? null)
      );
      if (unchanged) {
        return prev;
      }
      const next: LearningSessionState = {
        ...prev,
        ...defined,
        lastUpdated: timestamp
      };
      // 身份确定前（首帧）各页的 updateSession 只改内存，不落盘也不上报；
      // 身份确定后加载的会话会覆盖它
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
    // Also clear on server
    saveChainRef.current = saveChainRef.current.then(() => saveLearningState(userId, {
      wordId: null,
      word: null,
      module: null,
      vksLevel: null,
      recommendationId: null
    })).catch(err => {
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
    restored,
    serverStateLoaded,
    updateSession,
    clearSession
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
