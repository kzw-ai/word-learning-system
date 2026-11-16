// 源文件：utils/timeTracker.ts（网页版）。RN 版：DOM 事件（visibilitychange/mouse/keyboard/beforeunload）
// 换成 AppState；v1 策略「App 在前台就算在学」，idle_gap 只在切后台时产生。后端协议不变。
import { AppState, type AppStateStatus } from 'react-native';
import { getApiBaseUrl } from './apiClient';
import { authenticatedFetch } from './authClient';
import { getAuthHeaders } from './authHeaders';
import { DEFAULT_IDLE_CAP_SECONDS, splitGap } from './activeTime';

export interface TimeTrackingConfig {
  userId: string;
  wordId: number;
  moduleType: string; // 'entrance', 'character', 'word', 'collocation', 'sentence', 'exercise'
  sessionType: string; // 'learning', 'exercise', 'review', 'test'
  initialLevel?: string;
  recommendationId?: number;
  /** 会话状态是否已水合完毕。false 时 useTimeTracking 不建追踪器。 */
  ready?: boolean;
  /** 两次操作之间最多算多少秒有效时长（见 activeTime.ts）。 */
  idleCapSeconds?: number;
  /** 同一个词换了内容要另记一个会话时改变它。 */
  sessionKey?: string | number;
}

export interface LearningEvent {
  type: string;
  target?: string;
  data?: any;
  timestamp: Date;
}

export interface ExerciseData {
  questionId: string;
  questionType: string;
  questionContent?: string;
  userAnswer: string;
  correctAnswer: string;
  isCorrect: boolean;
  startTime: Date;
  endTime: Date;
  hesitationCount?: number;
  confidenceLevel?: number;
  attemptCount?: number;
}

export class TimeTracker {
  private static readonly MAX_QUEUED_EVENTS = 500;

  private sessionId: string;
  private startTime: Date;
  private activeTime = 0;
  private lastActiveTime: Date;
  private isActive = true;
  private events: LearningEvent[] = [];
  private config: TimeTrackingConfig;
  private apiBaseUrl: string;
  private batchEventTimer: ReturnType<typeof setInterval> | null = null;
  private disabled: boolean;
  private ended = false;
  private sessionStarted: Promise<boolean> = Promise.resolve(false);
  private readonly boundAppState = this.handleAppState.bind(this);
  private subscription: { remove: () => void } | null = null;

  constructor(config: TimeTrackingConfig, apiBaseUrl: string = getApiBaseUrl()) {
    this.config = config;
    this.apiBaseUrl = apiBaseUrl.replace(/\/$/, '');
    this.sessionId = this.generateSessionId();
    this.startTime = new Date();
    this.lastActiveTime = new Date();
    this.isActive = AppState.currentState === 'active';
    // 未登录也记录：后端凭 X-Guest-Id 识别访客身份。身份未确定时不建追踪器（由 ready 控制）。
    this.disabled = !config.userId;
    if (this.disabled) {
      console.info('⏸️ 身份尚未确定，学习时间追踪暂不上报');
    }
    this.initializeTracking();
  }

  private generateSessionId(): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substr(2, 9);
    return `${this.config.userId}_${this.config.wordId}_${timestamp}_${random}`;
  }

  private initializeTracking() {
    this.subscription = AppState.addEventListener('change', this.boundAppState);
    this.sessionStarted = this.startSession();
    this.batchEventTimer = setInterval(() => {
      this.sendBatchEvents();
    }, 30000);
  }

  dispose() {
    this.subscription?.remove();
    this.subscription = null;
    if (this.batchEventTimer) {
      clearInterval(this.batchEventTimer);
      this.batchEventTimer = null;
    }
  }

  private async startSession(): Promise<boolean> {
    if (this.disabled) return false;
    try {
      const response = await authenticatedFetch('/api/learning/session/start', {
        method: 'POST',
        body: JSON.stringify({
          sessionId: this.sessionId,
          userId: this.config.userId,
          wordId: this.config.wordId,
          sessionType: this.config.sessionType,
          moduleType: this.config.moduleType,
          initialLevel: this.config.initialLevel,
          recommendationId: this.config.recommendationId,
          startTime: this.startTime.toISOString(),
          deviceType: 'mobile',
        }),
      });
      const result = await response.json();
      if (result.success) {
        this.trackEvent('session_start', 'timetracker', { config: this.config, deviceType: 'mobile' });
        return true;
      }
      console.error('❌ Failed to start session:', result.error);
    } catch (error) {
      console.error('❌ Failed to start session:', error);
    }
    return false;
  }

  /** 会话建好之后才得知 VKS 档位时补写。 */
  public async setInitialLevel(level: string, wordId: number) {
    if (this.disabled || this.config.initialLevel || wordId !== this.config.wordId) return;
    this.config = { ...this.config, initialLevel: level };
    await this.sessionStarted;
    try {
      await authenticatedFetch('/api/learning/session/initial-level', {
        method: 'POST',
        body: JSON.stringify({ sessionId: this.sessionId, initialLevel: level }),
      });
    } catch (error) {
      console.error('❌ Failed to set initial level:', error);
    }
  }

  public trackEvent(eventType: string, target?: string, data?: any) {
    const event: LearningEvent = { type: eventType, target, data, timestamp: new Date() };
    this.events.push(event);
  }

  public async trackExercise(exerciseData: ExerciseData) {
    if (this.disabled) return;
    await this.sessionStarted;
    try {
      const response = await authenticatedFetch('/api/learning/exercise/record', {
        method: 'POST',
        body: JSON.stringify({
          sessionId: this.sessionId,
          userId: this.config.userId,
          questionId: exerciseData.questionId,
          questionType: exerciseData.questionType,
          questionContent: exerciseData.questionContent,
          userAnswer: exerciseData.userAnswer,
          correctAnswer: exerciseData.correctAnswer,
          isCorrect: exerciseData.isCorrect,
          startTime: exerciseData.startTime.toISOString(),
          endTime: exerciseData.endTime.toISOString(),
          responseTimeSeconds: (exerciseData.endTime.getTime() - exerciseData.startTime.getTime()) / 1000,
          hesitationCount: exerciseData.hesitationCount || 0,
          confidenceLevel: exerciseData.confidenceLevel,
          attemptCount: exerciseData.attemptCount ?? 1,
          isFirstAttempt: (exerciseData.attemptCount ?? 1) === 1,
        }),
      });
      const result = await response.json();
      if (!result.success) {
        console.error('❌ Failed to track exercise:', result.error);
      }
    } catch (error) {
      console.error('❌ Failed to track exercise:', error);
    }
  }

  private accrue(now: Date) {
    const capMs = (this.config.idleCapSeconds ?? DEFAULT_IDLE_CAP_SECONDS) * 1000;
    const { activeMs, idleMs } = splitGap(now.getTime() - this.lastActiveTime.getTime(), capMs);
    this.activeTime += activeMs;
    if (idleMs > 0) {
      this.trackEvent('idle_gap', 'appstate', {
        idleSeconds: Math.round(idleMs / 1000),
        capSeconds: capMs / 1000,
        lastActivityAt: this.lastActiveTime.toISOString(),
      });
    }
    this.lastActiveTime = now;
  }

  private handleAppState(nextState: AppStateStatus) {
    if (this.ended) return;
    if (nextState === 'active') {
      this.isActive = true;
      this.lastActiveTime = new Date();
      this.trackEvent('app_focus', 'appstate');
    } else {
      // 切后台之前把最后一次操作到 now 的间隔也算上，然后 flush（iOS 后台定时器会被挂起）。
      if (this.isActive) this.accrue(new Date());
      this.isActive = false;
      this.trackEvent('app_blur', 'appstate');
      this.sendBatchEvents();
    }
  }

  public async endSession(completed: boolean = true) {
    if (this.ended) return;
    this.ended = true;

    const endTime = new Date();
    if (this.isActive) this.accrue(endTime);
    const totalDuration = Math.round((endTime.getTime() - this.startTime.getTime()) / 1000);
    const activeDuration = Math.round(this.activeTime / 1000);

    this.trackEvent('session_end', 'timetracker', {
      completed,
      totalDuration,
      activeDuration,
      eventCount: this.events.length,
    });

    if (this.disabled) {
      if (this.batchEventTimer) {
        clearInterval(this.batchEventTimer);
        this.batchEventTimer = null;
      }
      return;
    }
    try {
      const response = await authenticatedFetch('/api/learning/session/end', {
        method: 'POST',
        body: JSON.stringify({
          sessionId: this.sessionId,
          userId: this.config.userId,
          endTime: endTime.toISOString(),
          durationSeconds: totalDuration,
          activeTimeSeconds: activeDuration,
          completed,
          eventCount: this.events.length,
        }),
      });
      const result = await response.json();
      if (!result.success) {
        console.error('❌ Failed to end session:', result.error);
      }
      await this.sendBatchEvents();
    } catch (error) {
      console.error('❌ Failed to end session:', error);
    }
    if (this.batchEventTimer) {
      clearInterval(this.batchEventTimer);
      this.batchEventTimer = null;
    }
  }

  private async sendBatchEvents() {
    if (this.events.length === 0) return;
    const eventsToSend = [...this.events];
    this.events = [];
    try {
      const response = await fetch(`${this.apiBaseUrl}/api/learning/events/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(await getAuthHeaders()) },
        body: JSON.stringify({
          sessionId: this.sessionId,
          userId: this.config.userId,
          events: eventsToSend.map(e => ({
            type: e.type,
            target: e.target,
            data: e.data,
            timestamp: e.timestamp.toISOString(),
          })),
        }),
      });
      const result = await response.json();
      if (!result.success) {
        this.requeueFailed(eventsToSend);
      }
    } catch {
      this.requeueFailed(eventsToSend);
    }
  }

  private requeueFailed(failedEvents: LearningEvent[]) {
    const merged = [...failedEvents, ...this.events];
    const overflow = merged.length - TimeTracker.MAX_QUEUED_EVENTS;
    this.events = overflow > 0 ? merged.slice(overflow) : merged;
  }

  public getSessionInfo() {
    const now = new Date();
    const duration = Math.round((now.getTime() - this.startTime.getTime()) / 1000);
    const activeDuration = Math.round(this.activeTime / 1000);
    return {
      sessionId: this.sessionId,
      startTime: this.startTime,
      duration,
      activeDuration,
      activeRate: duration > 0 ? activeDuration / duration : 0,
      eventCount: this.events.length,
      isActive: this.isActive,
    };
  }

  public updateConfig(newConfig: Partial<TimeTrackingConfig>) {
    this.config = { ...this.config, ...newConfig };
    this.trackEvent('config_update', 'timetracker', newConfig);
  }
}

export const createTimeTracker = (config: TimeTrackingConfig) => new TimeTracker(config);

export default TimeTracker;
