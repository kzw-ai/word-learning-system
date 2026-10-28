/**
 * React时间追踪Hooks
 * 封装TimeTracker类为React Hook，提供便捷的时间追踪功能
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { TimeTracker, TimeTrackingConfig, ExerciseData } from '@/utils/timeTracker';

export interface UseTimeTrackingReturn {
  isTracking: boolean;
  sessionInfo: any;
  trackEvent: (eventType: string, target?: string, data?: any) => void;
  trackExercise: (exerciseData: ExerciseData) => Promise<void>;
  endSession: (completed?: boolean) => Promise<void>;
  updateConfig: (newConfig: Partial<TimeTrackingConfig>) => void;
}

/**
 * 主要的时间追踪Hook
 */
export const useTimeTracking = (config: TimeTrackingConfig): UseTimeTrackingReturn => {
  const trackerRef = useRef<TimeTracker | null>(null);
  // 追踪器建好之前的作答，连同作答时的身份与词：补发时只发给同一身份、同一个词的会话
  const pendingExercisesRef = useRef<{ userId: string; wordId: number; exercise: ExerciseData }[]>([]);
  const configRef = useRef(config);
  configRef.current = config;
  const [isTracking, setIsTracking] = useState(false);
  const [sessionInfo, setSessionInfo] = useState<any>(null);

  useEffect(() => {
    // 等会话状态从 localStorage 水合完毕再建追踪器。
    // TimeTracker 的构造函数会立刻发 startSession，提前创建会先写出一条
    // initial_level 为 NULL 的会话，随后水合又把它 end 掉再建一条，
    // 每次整页加载凭空多出 0 秒的幽灵会话，污染「学习次数/总时长」统计。
    if (config.ready === false) {
      return;
    }

    // 开始追踪
    trackerRef.current = new TimeTracker(config);
    setIsTracking(true);
    // 补发追踪器建好之前的作答（TimeTracker 会先等会话在后端建好）。身份或词对不上的
    // 丢弃：那是用户已经离开的那个词的题，不能记进这个词的会话
    const pending = pendingExercisesRef.current.splice(0);
    pending
      .filter((item) => item.userId === config.userId && item.wordId === config.wordId)
      .forEach((item) => trackerRef.current?.trackExercise(item.exercise));

    // 定期更新会话信息
    const interval = setInterval(() => {
      if (trackerRef.current) {
        setSessionInfo(trackerRef.current.getSessionInfo());
      }
    }, 5000); // 每5秒更新一次

    return () => {
      // 组件卸载时结束追踪。dispose() 必须调用，否则旧实例被 document/window
      // 的监听器强引用而无法回收，还会在 beforeunload 时重复上报
      if (trackerRef.current) {
        trackerRef.current.endSession(true);
        trackerRef.current.dispose();
        trackerRef.current = null;
      }
      setIsTracking(false);
      clearInterval(interval);
    };
    // 依赖里放 ready 而不是 initialLevel：档位只在 ready 翻转的那一次被读取，
    // 之后档位再变化也不重建追踪器（否则每变一次就多一条幽灵会话）。
  }, [config.userId, config.wordId, config.moduleType, config.sessionType, config.ready]);

  // 追踪器建好之后档位才到（换设备时服务器状态晚于本地状态返回）：补写进当前会话。
  // 追踪器本来就带着这个档位时 setInitialLevel 什么也不做
  useEffect(() => {
    if (trackerRef.current && config.initialLevel) {
      trackerRef.current.setInitialLevel(config.initialLevel, config.wordId);
    }
  }, [config.initialLevel, config.wordId]);

  const trackEvent = useCallback((eventType: string, target?: string, data?: any) => {
    if (trackerRef.current) {
      trackerRef.current.trackEvent(eventType, target, data);
    }
  }, []);

  const trackExercise = useCallback(async (exerciseData: ExerciseData) => {
    if (trackerRef.current) {
      await trackerRef.current.trackExercise(exerciseData);
    } else {
      // 追踪器还在等会话状态就绪（例如服务器状态恢复中）时作答不能丢：先存着，建好后补发
      pendingExercisesRef.current.push({
        userId: configRef.current.userId,
        wordId: configRef.current.wordId,
        exercise: exerciseData
      });
    }
  }, []);

  const endSession = useCallback(async (completed: boolean = true) => {
    if (trackerRef.current) {
      await trackerRef.current.endSession(completed);
      setIsTracking(false);
    }
  }, []);

  const updateConfig = useCallback((newConfig: Partial<TimeTrackingConfig>) => {
    if (trackerRef.current) {
      trackerRef.current.updateConfig(newConfig);
    }
  }, []);

  return {
    isTracking,
    sessionInfo,
    trackEvent,
    trackExercise,
    endSession,
    updateConfig
  };
};

/**
 * 专门用于练习题计时的Hook
 */
export interface UseExerciseTimerReturn {
  startTimer: () => void;
  submitAnswer: () => void;
  recordHesitation: () => void;
  getResponseTime: () => number;
  hesitationCount: number;
  isAnswered: boolean;
  startTime: Date | null;
  endTime: Date | null;
  getCurrentTimer: () => number; // 当前计时器（秒）
}

export const useExerciseTimer = (): UseExerciseTimerReturn => {
  const [startTime, setStartTime] = useState<Date | null>(null);
  const [endTime, setEndTime] = useState<Date | null>(null);
  const [hesitationCount, setHesitationCount] = useState(0);
  const [isAnswered, setIsAnswered] = useState(false);
  const [currentTimer, setCurrentTimer] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const startTimer = useCallback(() => {
    const now = new Date();
    setStartTime(now);
    setEndTime(null);
    setHesitationCount(0);
    setIsAnswered(false);
    setCurrentTimer(0);

    // 启动实时计时器
    timerRef.current = setInterval(() => {
      setCurrentTimer(prev => prev + 0.1);
    }, 100);
  }, []);

  const recordHesitation = useCallback(() => {
    setHesitationCount(prev => prev + 1);
  }, []);

  const submitAnswer = useCallback(() => {
    if (!isAnswered && startTime) {
      const now = new Date();
      setEndTime(now);
      setIsAnswered(true);
      
      // 停止计时器
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [isAnswered, startTime]);

  const getResponseTime = useCallback((): number => {
    if (startTime && endTime) {
      return (endTime.getTime() - startTime.getTime()) / 1000;
    }
    return 0;
  }, [startTime, endTime]);

  const getCurrentTimer = useCallback((): number => {
    return Math.round(currentTimer * 10) / 10; // 保留1位小数
  }, [currentTimer]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  return {
    startTimer,
    submitAnswer,
    recordHesitation,
    getResponseTime,
    hesitationCount,
    isAnswered,
    startTime,
    endTime,
    getCurrentTimer
  };
};

/**
 * 用于页面导航时的时间追踪Hook
 */
export interface UsePageTrackingReturn {
  trackPageEnter: (pageName: string) => void;
  trackPageLeave: (pageName: string) => void;
  trackNavigation: (from: string, to: string) => void;
}

export const usePageTracking = (timeTracker?: UseTimeTrackingReturn): UsePageTrackingReturn => {
  const trackPageEnter = useCallback((pageName: string) => {
    if (timeTracker) {
      timeTracker.trackEvent('page_enter', 'navigation', {
        pageName,
        timestamp: new Date().toISOString(),
        url: typeof window !== 'undefined' ? window.location.pathname : undefined
      });
    }
  }, [timeTracker]);

  const trackPageLeave = useCallback((pageName: string) => {
    if (timeTracker) {
      timeTracker.trackEvent('page_leave', 'navigation', {
        pageName,
        timestamp: new Date().toISOString()
      });
    }
  }, [timeTracker]);

  const trackNavigation = useCallback((from: string, to: string) => {
    if (timeTracker) {
      timeTracker.trackEvent('navigation', 'router', {
        from,
        to,
        timestamp: new Date().toISOString()
      });
    }
  }, [timeTracker]);

  return {
    trackPageEnter,
    trackPageLeave,
    trackNavigation
  };
};

/**
 * 用于按钮点击等交互事件的Hook
 */
export interface UseInteractionTrackingReturn {
  trackButtonClick: (buttonId: string, buttonText?: string, additionalData?: any) => void;
  trackInputChange: (inputId: string, inputType: string, value?: any) => void;
  trackAudioPlay: (audioId: string, audioType: string) => void;
  trackSelectionChange: (selectionType: string, oldValue?: any, newValue?: any) => void;
}

export const useInteractionTracking = (timeTracker?: UseTimeTrackingReturn): UseInteractionTrackingReturn => {
  const trackButtonClick = useCallback((buttonId: string, buttonText?: string, additionalData?: any) => {
    if (timeTracker) {
      timeTracker.trackEvent('button_click', buttonId, {
        buttonText,
        timestamp: new Date().toISOString(),
        ...additionalData
      });
    }
  }, [timeTracker]);

  const trackInputChange = useCallback((inputId: string, inputType: string, value?: any) => {
    if (timeTracker) {
      timeTracker.trackEvent('input_change', inputId, {
        inputType,
        value: typeof value === 'string' ? value.substring(0, 100) : value, // 限制长度
        timestamp: new Date().toISOString()
      });
    }
  }, [timeTracker]);

  const trackAudioPlay = useCallback((audioId: string, audioType: string) => {
    if (timeTracker) {
      timeTracker.trackEvent('audio_play', audioId, {
        audioType,
        timestamp: new Date().toISOString()
      });
    }
  }, [timeTracker]);

  const trackSelectionChange = useCallback((selectionType: string, oldValue?: any, newValue?: any) => {
    if (timeTracker) {
      timeTracker.trackEvent('selection_change', selectionType, {
        oldValue,
        newValue,
        timestamp: new Date().toISOString()
      });
    }
  }, [timeTracker]);

  return {
    trackButtonClick,
    trackInputChange,
    trackAudioPlay,
    trackSelectionChange
  };
};

/**
 * 综合Hook - 包含所有时间追踪功能
 */
export interface UseComprehensiveTrackingReturn extends UseTimeTrackingReturn {
  pageTracking: UsePageTrackingReturn;
  interactionTracking: UseInteractionTrackingReturn;
  exerciseTimer: UseExerciseTimerReturn;
}

export const useComprehensiveTracking = (config: TimeTrackingConfig): UseComprehensiveTrackingReturn => {
  const timeTracking = useTimeTracking(config);
  const pageTracking = usePageTracking(timeTracking);
  const interactionTracking = useInteractionTracking(timeTracking);
  const exerciseTimer = useExerciseTimer();

  return {
    ...timeTracking,
    pageTracking,
    interactionTracking,
    exerciseTimer
  };
};

export default useTimeTracking;
