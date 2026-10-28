import { useCallback, useEffect, useState } from 'react';
import { fetchWord } from '@/src/lib/apiClient';
import type { WordCharacter, WordResponse } from '@/src/lib/types';

const STORAGE_KEY = 'currentWordId';
const DEFAULT_WORD_ID = 1;

export interface WordData extends WordResponse {
  hanzi: string;
}

const deriveHanzi = (characters: WordCharacter[]) => {
  if (characters && characters.length > 0) {
    return characters.map((item) => item.character).join('');
  }
  return 'Word';
};

const normaliseWord = (raw: WordResponse): WordData => ({
  ...raw,
  hanzi: raw.hanzi ?? deriveHanzi(raw.characters),
});

const parseStoredId = (value: string | null): number | null => {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

export interface UseWordDataOptions {
  initialWordId?: number | null;
}

export const useWordData = (options: UseWordDataOptions = {}) => {
  const [wordId, setWordIdState] = useState<number | null>(options.initialWordId ?? null);
  const [word, setWord] = useState<WordData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [requestToken, setRequestToken] = useState(0);

  // 跟随调用方传入的词。各页传的是学习会话里的 wordId，首帧会话尚未从
  // localStorage 恢复时它是空的；只在挂载时读一次的话，整页加载（刷新、直达链接）
  // 会停在兜底词上：页面显示「发生」，练习却在考别的词，学习页还会把这个兜底词
  // 写回会话。依赖变化会取消上一个请求，兜底词的结果不会落地。
  const requestedId = options.initialWordId ?? null;
  useEffect(() => {
    if (requestedId !== null) {
      setWordIdState((current) => (current === requestedId ? current : requestedId));
    }
  }, [requestedId]);

  useEffect(() => {
    if (wordId !== null) {
      return;
    }

    if (typeof window === 'undefined') {
      return;
    }

    const stored = parseStoredId(window.localStorage.getItem(STORAGE_KEY));
    setWordIdState(stored ?? DEFAULT_WORD_ID);
  }, [wordId]);

  useEffect(() => {
    if (wordId === null) {
      return;
    }

    let isCancelled = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchWord(wordId);
        if (isCancelled) {
          return;
        }
        setWord(normaliseWord(result));
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(STORAGE_KEY, String(wordId));
        }
      } catch (err) {
        if (isCancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
        setWord(null);
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    run();

    return () => {
      isCancelled = true;
    };
  }, [wordId, requestToken]);

  const setWordId = useCallback((id: number) => {
    setWordIdState(id);
    setRequestToken((token) => token + 1);
  }, []);

  const refresh = useCallback(() => {
    setRequestToken((token) => token + 1);
  }, []);

  return {
    wordId,
    setWordId,
    word,
    loading,
    error,
    refresh,
  };
};

export type UseWordDataValue = ReturnType<typeof useWordData>;
