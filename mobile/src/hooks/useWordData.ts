// 源文件：hooks/useWordData.ts（网页版）。RN 版：去掉 localStorage 兜底。
import { useCallback, useEffect, useState } from 'react';
import { fetchWord } from '@/lib/apiClient';
import type { WordCharacter, WordResponse } from '@/lib/types';

export interface WordData extends WordResponse {
  hanzi: string;
}

const deriveHanzi = (characters: WordCharacter[]) => {
  if (characters && characters.length > 0) {
    return characters.map(item => item.character).join('');
  }
  return 'Word';
};

const normaliseWord = (raw: WordResponse): WordData => ({
  ...raw,
  hanzi: raw.hanzi ?? deriveHanzi(raw.characters),
});

export interface UseWordDataOptions {
  initialWordId?: number | null;
}

export const useWordData = (options: UseWordDataOptions = {}) => {
  const [wordId, setWordIdState] = useState<number | null>(options.initialWordId ?? null);
  const [word, setWord] = useState<WordData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [requestToken, setRequestToken] = useState(0);

  // 跟随调用方传入的词。各页传的是学习会话里的 wordId，首帧会话尚未恢复时是空的。
  const requestedId = options.initialWordId ?? null;
  useEffect(() => {
    if (requestedId !== null) {
      setWordIdState(current => (current === requestedId ? current : requestedId));
    }
  }, [requestedId]);

  useEffect(() => {
    if (wordId === null) return;
    let isCancelled = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchWord(wordId);
        if (isCancelled) return;
        setWord(normaliseWord(result));
      } catch (err) {
        if (isCancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setWord(null);
      } finally {
        if (!isCancelled) setLoading(false);
      }
    };

    run();

    return () => {
      isCancelled = true;
    };
  }, [wordId, requestToken]);

  const setWordId = useCallback((id: number) => {
    setWordIdState(id);
    setRequestToken(token => token + 1);
  }, []);

  const refresh = useCallback(() => {
    setRequestToken(token => token + 1);
  }, []);

  return { wordId, setWordId, word, loading, error, refresh };
};

export type UseWordDataValue = ReturnType<typeof useWordData>;
