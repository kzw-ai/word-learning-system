import { useMemo, useCallback } from 'react';
import { useRouter } from 'next/router';
import { useLearningSession } from '@/src/context/LearningSessionContext';

export const moduleOrder = ['entrance', 'character', 'word', 'collocation', 'sentence', 'exercise', 'dashboard'] as const;

export const moduleRouteMap: Record<string, string> = {
  entrance: '/word-learning-entrance',
  character: '/character-learning',
  word: '/word-learning',
  collocation: '/collocation-learning',
  sentence: '/sentence-learning',
  exercise: '/exercise',
  dashboard: '/learning-dashboard'
};

export const moduleLabelMap: Record<string, string> = {
  entrance: 'Self-check',
  character: 'Characters',
  word: 'Word',
  collocation: 'Collocations',
  sentence: 'Sentences',
  exercise: 'Practice',
  dashboard: 'Dashboard'
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

export interface NavigationTarget {
  key: string;
  label: string;
  path: string;
}

export const useLearningNavigation = (currentModule: string) => {
  const router = useRouter();
  const { updateSession } = useLearningSession();

  const canonical = normaliseModule(currentModule);

  const { previous, next } = useMemo(() => {
    const index = moduleOrder.indexOf(canonical as typeof moduleOrder[number]);
    const prevKey = index > 0 ? moduleOrder[index - 1] : null;
    const nextKey = index >= 0 && index < moduleOrder.length - 1 ? moduleOrder[index + 1] : null;

    const toNavigationTarget = (key: string | null): NavigationTarget | null => {
      if (!key) return null;
      const path = moduleRouteMap[key];
      if (!path) return null;
      return {
        key,
        path,
        label: moduleLabelMap[key] ?? key
      };
    };

    return {
      previous: toNavigationTarget(prevKey),
      next: toNavigationTarget(nextKey)
    };
  }, [canonical]);

  const goTo = useCallback((targetKey: string) => {
    updateSession({ module: targetKey });
    const path = moduleRouteMap[targetKey];
    if (path) {
      router.push(path);
    }
  }, [router, updateSession]);

  return {
    current: canonical,
    previous,
    next,
    goTo
  };
};

