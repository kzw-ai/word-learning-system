import React, { useEffect } from 'react';
import { WordHero, ExampleList, DefinitionBlock, CollocationList, CharacterBreakdown, RecapSection } from "@/components/learning/WordBlocks";
import StepProgress from "@/components/learning/StepProgress";
import { Button } from "@/components/ui/button";
import { useWordData } from '@/hooks/useWordData';
import { useLearningSession } from '@/src/context/LearningSessionContext';
import { isSingleCharacter, useLearningNavigation } from '@/src/hooks/useLearningNavigation';
import { useSlideIn, useSwipeNavigation } from '@/src/hooks/useSwipeNavigation';
import SwipeHint from '@/components/learning/SwipeHint';
import { useLearningContext } from '@/src/context/LearningContext';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';

export default function Component() {
  const { session: learningSession, hydrated: sessionHydrated, restored: sessionRestored, updateSession: updateLearningSession } = useLearningSession();
  const { word, loading, error } = useWordData({ initialWordId: learningSession.wordId ?? undefined });
  // 单字词跳过字页（字页和词页内容一样）
  const singleChar = isSingleCharacter(word);
  const { previous, next, goTo } = useLearningNavigation('sentence', { skipCharacter: singleChar });
  const { userId } = useLearningContext();

  const tracking = useComprehensiveTracking({
    userId,
    wordId: learningSession.wordId ?? 1,
    moduleType: 'sentence',
    // 从今日复习进来再学一遍记为复习（辨析页同此），和第一次学习分开
    sessionType: learningSession.reviewMode ? 'review' : 'learning',
    initialLevel: learningSession.vksLevel ?? undefined,
    recommendationId: learningSession.recommendationId ?? undefined,
    // 等服务器状态恢复完再建会话：档位与推荐可能来自另一台设备
    ready: sessionHydrated && sessionRestored
  });
  const { pageTracking, interactionTracking, trackEvent } = tracking;

  useEffect(() => {
    pageTracking.trackPageEnter('sentence-learning');
    return () => {
      pageTracking.trackPageLeave('sentence-learning');
    };
  }, [pageTracking]);

  useEffect(() => {
    updateLearningSession({ module: 'sentence' });
  }, [updateLearningSession]);

  useEffect(() => {
    if (word) {
      updateLearningSession({ wordId: word.id, word: word.hanzi });
    }
  }, [word, updateLearningSession]);

  const handleNavigate = (direction: 'previous' | 'next') => {
    const target = direction === 'previous' ? previous : next;
    if (!target) return;
    interactionTracking.trackButtonClick(`navigate-${direction}`, target.label);
    trackEvent('module_navigate', 'sentence', { direction, to: target.key });
    goTo(target.key);
  };

  // 左滑 / → 下一步，右滑 / ← 上一步；词加载出来以后才能翻
  useSwipeNavigation(handleNavigate, Boolean(word));
  const slideIn = useSlideIn();

  const renderBody = () => {
    if (loading) {
      return (
        <div className="flex-1 p-3 flex flex-col justify-center items-center text-gray-500 text-sm">
          Loading example sentences…
        </div>
      );
    }

    if (error || !word) {
      return (
        <div className="flex-1 p-3 flex flex-col justify-center items-center text-red-500 text-sm text-center">
          Couldn't load the example sentences. Please try again later.
        </div>
      );
    }

    return (
      <div className={`flex-1 px-5 flex flex-col overflow-y-auto custom-scrollbar relative z-20 ${slideIn}`}>
        <div className="flex-1 space-y-4">
          <div className="glass-panel p-6 short:p-4 rounded-3xl shadow-lg border border-white/60 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-100 rounded-full mix-blend-multiply filter blur-2xl opacity-50 pointer-events-none -mr-10 -mt-10"></div>
            <div className="relative z-10 space-y-6 short:space-y-4">
              <WordHero word={word} />
              <ExampleList word={word} />
            </div>
          </div>
          {/* 前面步骤的内容折叠在这里，跳级进来的学习者也能补看 */}
          <RecapSection labels={singleChar ? ["Meaning", "Collocations"] : ["Meaning", "Collocations", "Characters"]}>
            <DefinitionBlock word={word} />
            <CollocationList word={word} />
            {!singleChar && <CharacterBreakdown word={word} />}
          </RecapSection>
          <div className="h-6 w-full shrink-0"></div>
        </div>

        {/* 底部按钮区域保持为单大绿色 CONTINUE 按钮以符合原型图 */}
        {/* 固定在屏幕底部：小屏手机上内容比屏幕高时，按钮也一直看得到（内容在它后面滚动） */}
        <div className="sticky bottom-0 bg-slate-100/95 backdrop-blur-sm border-t border-slate-200/70 shadow-[0_-8px_16px_-12px_rgba(15,23,42,0.25)] pt-3 w-full z-30 px-5 pb-[calc(env(safe-area-inset-bottom)+1rem)] short:pb-[calc(env(safe-area-inset-bottom)+0.75rem)]">
          <SwipeHint />
          <Button
              className="w-full h-12 rounded-2xl border-none shadow-md shadow-indigo-500/20 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 active:scale-[0.99] text-white font-bold tracking-wider text-base transition-all duration-200"
              onClick={() => handleNavigate("next")}
            >
              CONTINUE
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-4 flex flex-col relative z-20">
          <div className="px-5 mb-3">
            <div className="flex justify-between items-center">
              <Button
                className="h-9 px-3 rounded-xl bg-white/80 hover:bg-white border border-slate-200/70 shadow-sm text-indigo-700 text-sm font-semibold"
                variant="ghost"
                disabled={!previous}
                onClick={() => handleNavigate('previous')}
              >
                ← {previous?.label || 'Back'}
              </Button>
              <h1 className="text-xl font-extrabold text-slate-900 tracking-tight leading-none pt-1">Sentences</h1>
              <Button
                className="h-9 px-3 rounded-xl bg-white/80 hover:bg-white border border-slate-200/70 shadow-sm text-indigo-700 text-sm font-semibold"
                variant="ghost"
                disabled={!next}
                onClick={() => handleNavigate('next')}
              >
                {next?.label || 'Finish'} →
              </Button>
            </div>
            <div className="mt-3">
              <StepProgress current="sentence" entry={learningSession.entryModule} skipCharacter={singleChar} />
            </div>
          </div>
          
          {renderBody()}

          {/* Decorative blurs */}
          <div className="absolute top-1/3 -right-12 w-48 h-48 bg-indigo-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>
          <div className="absolute bottom-1/3 -left-12 w-48 h-48 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>
        </div>
      </div>
    </div>
  );
}
