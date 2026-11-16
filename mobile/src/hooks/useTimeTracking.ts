// 源文件：hooks/useTimeTracking.ts（网页版）。RN 版：TimeTracker 内部用 AppState，hook 结构照搬。
import { useCallback, useEffect, useRef, useState } from 'react';
import { TimeTracker, type TimeTrackingConfig, type ExerciseData } from '@/lib/timeTracker';

export interface UseTimeTrackingReturn {
  isTracking: boolean;
  sessionInfo: any;
  trackEvent: (eventType: string, target?: string, data?: any) => void;
  trackExercise: (exerciseData: ExerciseData) => Promise<void>;
  endSession: (completed?: boolean) => Promise<void>;
  updateConfig: (newConfig: Partial<TimeTrackingConfig>) => void;
}

export const useTimeTracking = (config: TimeTrackingConfig): UseTimeTrackingReturn => {
  const trackerRef = useRef<TimeTracker | null>(null);
  const pendingExercisesRef = useRef<{ userId: string; wordId: number; exercise: ExerciseData }[]>([]);
  const configRef = useRef(config);
  configRef.current = config;
  const [isTracking, setIsTracking] = useState(false);
  const [sessionInfo, setSessionInfo] = useState<any>(null);

  useEffect(() => {
    // 等会话状态水合完毕再建追踪器，避免先写出 initial_level 为 NULL 的幽灵会话。
    if (config.ready === false) return;

    trackerRef.current = new TimeTracker(config);
    setIsTracking(true);
    const pending = pendingExercisesRef.current.splice(0);
    pending
      .filter(item => item.userId === config.userId && item.wordId === config.wordId)
      .forEach(item => trackerRef.current?.trackExercise(item.exercise));

    const interval = setInterval(() => {
      if (trackerRef.current) setSessionInfo(trackerRef.current.getSessionInfo());
    }, 5000);

    return () => {
      if (trackerRef.current) {
        trackerRef.current.endSession(true);
        trackerRef.current.dispose();
        trackerRef.current = null;
      }
      setIsTracking(false);
      clearInterval(interval);
    };
  }, [config.userId, config.wordId, config.sessionKey, config.moduleType, config.sessionType, config.ready]);

  // 追踪器建好之后档位才到：补写进当前会话。
  useEffect(() => {
    if (trackerRef.current && config.initialLevel) {
      trackerRef.current.setInitialLevel(config.initialLevel, config.wordId);
    }
  }, [config.initialLevel, config.wordId]);

  const trackEvent = useCallback((eventType: string, target?: string, data?: any) => {
    if (trackerRef.current) trackerRef.current.trackEvent(eventType, target, data);
  }, []);

  const trackExercise = useCallback(async (exerciseData: ExerciseData) => {
    if (trackerRef.current) {
      await trackerRef.current.trackExercise(exerciseData);
    } else {
      pendingExercisesRef.current.push({
        userId: configRef.current.userId,
        wordId: configRef.current.wordId,
        exercise: exerciseData,
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
    if (trackerRef.current) trackerRef.current.updateConfig(newConfig);
  }, []);

  return { isTracking, sessionInfo, trackEvent, trackExercise, endSession, updateConfig };
};

export interface UseExerciseTimerReturn {
  startTimer: () => void;
  submitAnswer: () => void;
  recordHesitation: () => void;
  getResponseTime: () => number;
  hesitationCount: number;
  isAnswered: boolean;
  startTime: Date | null;
  endTime: Date | null;
  getCurrentTimer: () => number;
}

/** 练习题计时：只存起止时间，用时现算，避免每秒重渲染。 */
export const useExerciseTimer = (): UseExerciseTimerReturn => {
  const [startTime, setStartTime] = useState<Date | null>(null);
  const [endTime, setEndTime] = useState<Date | null>(null);
  const [hesitationCount, setHesitationCount] = useState(0);
  const [isAnswered, setIsAnswered] = useState(false);

  const startTimer = useCallback(() => {
    const now = new Date();
    setStartTime(now);
    setEndTime(null);
    setHesitationCount(0);
    setIsAnswered(false);
  }, []);

  const recordHesitation = useCallback(() => {
    setHesitationCount(prev => prev + 1);
  }, []);

  const submitAnswer = useCallback(() => {
    if (!isAnswered && startTime) {
      const now = new Date();
      setEndTime(now);
      setIsAnswered(true);
    }
  }, [isAnswered, startTime]);

  const getResponseTime = useCallback((): number => {
    if (startTime && endTime) return (endTime.getTime() - startTime.getTime()) / 1000;
    return 0;
  }, [startTime, endTime]);

  const getCurrentTimer = useCallback((): number => {
    if (!startTime) return 0;
    const end = endTime ?? new Date();
    return Math.round((end.getTime() - startTime.getTime()) / 100) / 10;
  }, [startTime, endTime]);

  return {
    startTimer,
    submitAnswer,
    recordHesitation,
    getResponseTime,
    hesitationCount,
    isAnswered,
    startTime,
    endTime,
    getCurrentTimer,
  };
};

export interface UseComprehensiveTrackingReturn extends UseTimeTrackingReturn {
  exerciseTimer: UseExerciseTimerReturn;
}

export const useComprehensiveTracking = (config: TimeTrackingConfig): UseComprehensiveTrackingReturn => {
  const timeTracking = useTimeTracking(config);
  const exerciseTimer = useExerciseTimer();
  return { ...timeTracking, exerciseTimer };
};

export default useTimeTracking;
