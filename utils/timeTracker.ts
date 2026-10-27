/**
 * 学习时间追踪工具类
 * 用于记录用户学习行为和时间数据，支持自适应学习算法
 */
import { getApiBaseUrl } from '@/src/lib/apiClient';
import { authenticatedFetch } from '@/src/lib/authClient';

export interface TimeTrackingConfig {
  userId: string;
  wordId: number;
  moduleType: string; // 'entrance', 'character', 'word', 'collocation', 'sentence', 'exercise'
  sessionType: string; // 'learning', 'exercise', 'review', 'test'
  /**
   * 学习者在入口页对本词自评的 VKS 档位（A-E）。
   * 后端 learning_session.initial_level 早已就位，但此前前端从不发送，
   * 该列恒为 NULL，论文表 4.3 的头 5 个特征因此没有数据源。
   */
  initialLevel?: string;
  /**
   * 会话状态是否已从 localStorage 水合完毕。为 false 时 useTimeTracking 不创建
   * 追踪器——提前创建会先写出 initial_level 为 NULL 的幽灵会话。
   */
  ready?: boolean;
}

export interface LearningEvent {
  type: string;
  target?: string;
  data?: any;
  timestamp: Date;
  pageUrl?: string;
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
}

export class TimeTracker {
  /** 待发送事件队列的长度上限，防止后端持续失败时无限堆积 */
  private static readonly MAX_QUEUED_EVENTS = 500;

  /** 用于判定「用户仍在活动」的 DOM 事件 */
  private static readonly ACTIVITY_EVENTS = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];

  // 监听器必须持有稳定引用才能被 removeEventListener 摘掉
  private readonly boundVisibilityChange = this.handleVisibilityChange.bind(this);
  private readonly boundUserActivity = this.handleUserActivity.bind(this);
  private readonly boundPageUnload = this.handlePageUnload.bind(this);

  /** 会话是否已结束，防止同一 sessionId 被 end 两次 */
  private ended: boolean = false;

  private sessionId: string;
  private startTime: Date;
  private activeTime: number = 0;
  private lastActiveTime: Date;
  private isActive: boolean = true;
  private events: LearningEvent[] = [];
  private config: TimeTrackingConfig;
  private apiBaseUrl: string;
  private batchEventTimer: NodeJS.Timeout | null = null;
  private disabled: boolean = false; // 未登录时停用网络上报，避免 401

  constructor(config: TimeTrackingConfig, apiBaseUrl: string = getApiBaseUrl()) {
    this.config = config;
    this.apiBaseUrl = apiBaseUrl.replace(/\/$/, '');
    this.sessionId = this.generateSessionId();
    this.startTime = new Date();
    this.lastActiveTime = new Date();
    // 未登录的访客也记录：后端凭访客 cookie 识别身份（见 src/lib/guestIdentity.ts）。
    // 此前没有 session_token 就整个停用，而注册登录又跑不通，结果线上一条学习数据都没有
    this.disabled = typeof window === 'undefined' || !config.userId;
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
    // 页面可见性监听
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.boundVisibilityChange);

      // 用户活动监听
      TimeTracker.ACTIVITY_EVENTS.forEach(event => {
        document.addEventListener(event, this.boundUserActivity, true);
      });

      // 页面卸载监听
      window.addEventListener('beforeunload', this.boundPageUnload);
    }

    // 开始学习会话
    this.startSession();

    // 设置批量事件发送定时器
    this.batchEventTimer = setInterval(() => {
      this.sendBatchEvents();
    }, 30000); // 每30秒发送一次批量事件
  }

  /**
   * 解绑全部监听器并停掉定时器。
   * 此前监听器用的是 .bind(this) 生成的匿名函数且从不移除，每次重建追踪器都会
   * 留下一个被 document/window 强引用的僵尸实例：它仍在处理每一次 mousemove，
   * 并会在 beforeunload 时把已正常结束的会话重新改写成 completed=false。
   */
  dispose() {
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.boundVisibilityChange);
      TimeTracker.ACTIVITY_EVENTS.forEach(event => {
        document.removeEventListener(event, this.boundUserActivity, true);
      });
      window.removeEventListener('beforeunload', this.boundPageUnload);
    }

    if (this.batchEventTimer) {
      clearInterval(this.batchEventTimer);
      this.batchEventTimer = null;
    }
  }

  private async startSession() {
    if (this.disabled) return;
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
          startTime: this.startTime.toISOString(),
          deviceType: this.getDeviceType()
        })
      });

      const result = await response.json();
      if (result.success) {
        console.log('✅ Time tracking session started:', this.sessionId);
        this.trackEvent('session_start', 'timetracker', {
          config: this.config,
          deviceType: this.getDeviceType()
        });
      } else {
        console.error('❌ Failed to start session:', result.error);
      }
    } catch (error) {
      console.error('❌ Failed to start session:', error);
    }
  }

  /**
   * 记录学习事件
   */
  public trackEvent(eventType: string, target?: string, data?: any) {
    const event: LearningEvent = {
      type: eventType,
      target,
      data,
      timestamp: new Date(),
      pageUrl: typeof window !== 'undefined' ? window.location.pathname : undefined
    };
    
    this.events.push(event);
    
    console.log('📊 Event tracked:', eventType, target, data);
    
    // 立即发送重要事件
    if (['exercise_submit', 'module_complete', 'error', 'session_end'].includes(eventType)) {
      this.sendEvent(event);
    }
  }

  /**
   * 记录练习数据
   */
  public async trackExercise(exerciseData: ExerciseData) {
    if (this.disabled) return;
    try {
      const response = await authenticatedFetch('/api/learning/exercise/record', {
        method: 'POST',
        body: JSON.stringify({
          sessionId: this.sessionId,
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
          confidenceLevel: exerciseData.confidenceLevel
        })
      });

      const result = await response.json();
      if (result.success) {
        console.log('✅ Exercise tracked:', exerciseData.questionId);
        this.trackEvent('exercise_recorded', 'exercise', {
          questionId: exerciseData.questionId,
          isCorrect: exerciseData.isCorrect,
          responseTime: (exerciseData.endTime.getTime() - exerciseData.startTime.getTime()) / 1000
        });
      } else {
        console.error('❌ Failed to track exercise:', result.error);
      }
    } catch (error) {
      console.error('❌ Failed to track exercise:', error);
    }
  }

  private handleVisibilityChange() {
    if (typeof document !== 'undefined') {
      if (document.hidden) {
        this.isActive = false;
        this.trackEvent('page_blur', 'document');
      } else {
        this.isActive = true;
        this.lastActiveTime = new Date();
        this.trackEvent('page_focus', 'document');
      }
    }
  }

  private handleUserActivity() {
    if (this.isActive) {
      const now = new Date();
      this.activeTime += now.getTime() - this.lastActiveTime.getTime();
      this.lastActiveTime = now;
    }
  }

  private handlePageUnload() {
    this.endSession(false); // 页面卸载时标记为未完成
  }

  /**
   * 结束学习会话
   */
  public async endSession(completed: boolean = true) {
    // 幂等：僵尸实例的 beforeunload 会重复调用，把已结束的会话改写成未完成
    if (this.ended) {
      return;
    }
    this.ended = true;

    const endTime = new Date();
    const totalDuration = Math.round((endTime.getTime() - this.startTime.getTime()) / 1000);
    const activeDuration = Math.round(this.activeTime / 1000);

    this.trackEvent('session_end', 'timetracker', {
      completed,
      totalDuration,
      activeDuration,
      eventCount: this.events.length
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
          endTime: endTime.toISOString(),
          durationSeconds: totalDuration,
          activeTimeSeconds: activeDuration,
          completed,
          eventCount: this.events.length
        })
      });

      const result = await response.json();
      if (result.success) {
        console.log('✅ Session ended successfully:', this.sessionId);
      } else {
        console.error('❌ Failed to end session:', result.error);
      }

      // 发送剩余的批量事件
      await this.sendBatchEvents();

    } catch (error) {
      console.error('❌ Failed to end session:', error);
    }

    // 清理定时器
    if (this.batchEventTimer) {
      clearInterval(this.batchEventTimer);
      this.batchEventTimer = null;
    }
  }

  private async sendEvent(event: LearningEvent) {
    try {
      // 对于单个重要事件，可以考虑单独发送
      console.log('📤 Sending critical event:', event.type);
    } catch (error) {
      console.error('❌ Failed to send event:', error);
    }
  }

  private async sendBatchEvents() {
    if (this.events.length === 0) return;

    const eventsToSend = [...this.events];
    this.events = [];

    try {
      console.log('📦 Sending batch events:', eventsToSend.length);
      
      const response = await fetch(`${this.apiBaseUrl}/api/learning/events/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: this.sessionId,
          events: eventsToSend.map(e => ({
            type: e.type,
            target: e.target,
            data: e.data,
            pageUrl: e.pageUrl,
            timestamp: e.timestamp.toISOString()
          }))
        })
      });

      const result = await response.json();
      if (result.success) {
        console.log(`✅ Batch events sent: ${result.count} recorded`);
      } else {
        console.error('❌ Failed to send batch events:', result.error);
        // 发送失败则重新加回队列
        this.requeueFailed(eventsToSend);
      }
    } catch (error) {
      console.error('❌ Failed to send batch events:', error);
      // 网络错误也重新加回队列
      this.requeueFailed(eventsToSend);
    }
  }

  /**
   * 把发送失败的事件放回队列头部，并限制队列长度。
   * 后端持续报错时（如 5xx）定时器会不断重发，无上限会让队列无限膨胀。
   * 超出上限时丢弃最旧的事件——新事件对分析更有价值。
   */
  private requeueFailed(failedEvents: LearningEvent[]) {
    const merged = [...failedEvents, ...this.events];
    const overflow = merged.length - TimeTracker.MAX_QUEUED_EVENTS;

    if (overflow > 0) {
      console.warn(`⚠️ 事件队列超过 ${TimeTracker.MAX_QUEUED_EVENTS} 条上限，丢弃最旧的 ${overflow} 条`);
      this.events = merged.slice(overflow);
    } else {
      this.events = merged;
    }
  }

  private getDeviceType(): string {
    if (typeof navigator !== 'undefined') {
      if (/Mobi|Android/i.test(navigator.userAgent)) {
        return 'mobile';
      }
    }
    return 'web';
  }

  /**
   * 获取会话信息
   */
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
      isActive: this.isActive
    };
  }

  /**
   * 手动更新配置（例如切换到不同模块）
   */
  public updateConfig(newConfig: Partial<TimeTrackingConfig>) {
    this.config = { ...this.config, ...newConfig };
    this.trackEvent('config_update', 'timetracker', newConfig);
  }
}

// 导出工具函数
export const createTimeTracker = (config: TimeTrackingConfig) => {
  return new TimeTracker(config);
};

export default TimeTracker;
