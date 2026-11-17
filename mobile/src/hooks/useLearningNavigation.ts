// 源文件：src/hooks/useLearningNavigation.ts（网页版）。RN 版：next/router → expo-router。
import { useCallback, useMemo } from 'react';
import { useRouter } from 'expo-router';
import { useLearningSession } from '@/context/LearningSessionContext';

export const moduleOrder = ['entrance', 'character', 'word', 'collocation', 'sentence', 'exercise', 'dashboard'] as const;

export const moduleRouteMap: Record<string, string> = {
  entrance: '/word-learning-entrance',
  character: '/character-learning',
  word: '/word-learning',
  collocation: '/collocation-learning',
  sentence: '/sentence-learning',
  exercise: '/exercise',
  dashboard: '/learning-dashboard',
};

export const moduleLabelMap: Record<string, string> = {
  entrance: 'Self-check',
  character: 'Characters',
  word: 'Word',
  collocation: 'Collocations',
  sentence: 'Sentences',
  exercise: 'Practice',
  dashboard: 'Dashboard',
};

const normaliseModule = (value: string) => {
  const lower = value.toLowerCase();
  if (lower.includes('character')) return 'character';
  if (lower.includes('word')) return 'word';
  if (lower.includes('collocation')) return 'collocation';
  if (lower.includes('sentence')) return 'sentence';
  if (lower.includes('exercise')) return 'exercise';
  if (lower.includes('dashboard')) return 'dashboard';
  if (lower.includes('entrance')) return 'entrance';
  return lower;
};

export const resolveModuleLabel = (module?: string | null) => {
  if (!module) return null;
  const key = normaliseModule(module);
  return moduleLabelMap[key] ?? module;
};

/** 单字词（如「得」）拆不出字：字页和词页内容一样，跳过字页 */
export const isSingleCharacter = (word?: { characters?: unknown[] } | null) =>
  (word?.characters?.length ?? 0) === 1;

export interface NavigationTarget {
  key: string;
  label: string;
  path: string;
}

export const useLearningNavigation = (currentModule: string, { skipCharacter = false }: { skipCharacter?: boolean } = {}) => {
  const router = useRouter();
  const { updateSession } = useLearningSession();

  const canonical = normaliseModule(currentModule);
  const order: readonly string[] = useMemo(
    () => (skipCharacter ? moduleOrder.filter(key => key !== 'character') : moduleOrder),
    [skipCharacter]
  );

  const { previous, next } = useMemo(() => {
    const index = order.indexOf(canonical);
    const prevKey = index > 0 ? order[index - 1] : null;
    const nextKey = index >= 0 && index < order.length - 1 ? order[index + 1] : null;

    const toNavigationTarget = (key: string | null): NavigationTarget | null => {
      if (!key) return null;
      const path = moduleRouteMap[key];
      if (!path) return null;
      return { key, path, label: moduleLabelMap[key] ?? key };
    };

    return { previous: toNavigationTarget(prevKey), next: toNavigationTarget(nextKey) };
  }, [canonical, order]);

  const goTo = useCallback((targetKey: string) => {
    updateSession({ module: targetKey });
    const path = moduleRouteMap[targetKey];
    if (path) {
      // 学习步骤之间用 replace，栈里只保留「首页 → 当前步骤」，
      // 避免来回切把旧页面一层层压在栈里（旧页面的计时/事件 hook 还会跑）。
      router.replace(path as any);
    }
  }, [router, updateSession]);

  return { current: canonical, previous, next, goTo };
};
