// 源文件：src/lib/types.ts（网页版）。纯类型定义，改动需与网页版同步。
export interface WordCharacter {
  character: string;
  pinyin: string;
  definition: string;
  audio: string;
}

export interface WordCollocation {
  collocation: string;
  translation: string;
  audio: string;
}

export interface WordExample {
  sentence: string;
  pinyin: string;
  translation: string;
  audio: string;
}

export interface WordResponse {
  id: number;
  pinyin: string;
  definition: string;
  hanzi?: string;
  /** 整词发音地址（/api/audio/<指纹>.mp3）；空字符串表示没有音频文件，用 TTS 朗读 */
  audio?: string;
  examples: WordExample[];
  collocations: WordCollocation[];
  characters: WordCharacter[];
}

export interface WordSummary {
  id: number;
  pinyin: string;
  definition: string;
}

export type ExerciseQuestionType = 'definition' | 'collocation' | 'fill_word' | 'choose_word';

export interface ExerciseQuestionPayload {
  id: string;
  type: ExerciseQuestionType;
  question: string;
  options: string[];
  /** 中文选项的发音地址；没有的选项用 TTS 朗读 */
  optionAudio?: Record<string, string>;
  /** 搭配题：这条搭配的英文意思，显示在题干下面 */
  gloss?: string | null;
  correctAnswer: string;
  feedback?: string;
}

export interface ExerciseSetResponse {
  wordId: number;
  word: string;
  definition: string;
  options: string[];
  questionCount: number;
  questions: ExerciseQuestionPayload[];
}

export interface UserProfileSummary {
  userId: string;
  username?: string;
  languageLevel?: string;
  nativeLanguage?: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  wordsStudied?: number;
  lastStudied?: string | null;
  lastSession?: {
    wordId?: number | null;
    word?: string | null;
    moduleType?: string | null;
    sessionType?: string | null;
    startedAt?: string | null;
  };
}

export interface RecentSessionSummary {
  sessionId: string;
  wordId?: number | null;
  word?: string | null;
  moduleType?: string | null;
  sessionType?: string | null;
  startTime?: string | null;
  endTime?: string | null;
  durationSeconds?: number | null;
}

// —— 今日复习 / 学习看板 ——
export interface ReviewItem {
  word_id: number;
  word: string;
  pinyin?: string;
  mastery_level: number;
  days_overdue: number;
  review_count: number;
  priority_score: number;
  recommended_module: string;
  /** 还要复习几次（各题型中最多的那个），0 表示已达标、进入长期巩固 */
  reviews_remaining?: number;
  /** 还需复习的题型 */
  review_types?: string[];
}

export interface Recommendation {
  type: string;
  priority: string;
  /** 暂时没有任务（all_caught_up）时为空 */
  word_id: number | null;
  word?: string;
  reason: string;
  recommended_module: string | null;
  confidence: number;
  estimated_time: number;
  recommendationId?: number | null;
  next_review_at?: string | null;
}

export interface DashboardData {
  overallProgress: {
    totalWords: number;
    hskLevel?: 3 | 4;
    levels?: Record<string, { words: number; studied: number }>;
    studiedWords: number;
    masteredWords: number;
    averageMastery: number;
  };
  todayStats: {
    studyTimeMinutes: number;
    wordsReviewed: number;
    exercisesCompleted: number;
    averageAccuracy: number;
  };
  recommendations: Recommendation[];
  dueReviews: number;
  strengths: string[];
  weaknesses: string[];
}
