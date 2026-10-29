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
  /** 整词发音地址（/api/audio/<指纹>.mp3）；空字符串表示没有音频文件，用浏览器朗读 */
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
