import React, { useEffect } from 'react';
import { WordHero, DefinitionBlock, CharacterBreakdown, RecapSection } from "@/components/learning/WordBlocks";
import StepProgress from "@/components/learning/StepProgress";
import { Button } from "@/components/ui/button";
import { useWordData } from '@/hooks/useWordData';
import { useLearningSession } from '@/src/context/LearningSessionContext';
import { useLearningNavigation } from '@/src/hooks/useLearningNavigation';
import { useLearningContext } from '@/src/context/LearningContext';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import ReviewReminder from '@/components/ReviewReminder';

export default function Component() {
  const { session: learningSession, hydrated: sessionHydrated, restored: sessionRestored, updateSession: updateLearningSession } = useLearningSession();
  const { userId } = useLearningContext();
  const { word, loading, error } = useWordData({ initialWordId: learningSession.wordId ?? undefined });
  const { previous, next, goTo } = useLearningNavigation('word');

  const tracking = useComprehensiveTracking({
    userId,
    wordId: learningSession.wordId ?? 1,
    moduleType: 'word',
    sessionType: 'learning',
    initialLevel: learningSession.vksLevel ?? undefined,
    recommendationId: learningSession.recommendationId ?? undefined,
    // 等服务器状态恢复完再建会话：档位与推荐可能来自另一台设备
    ready: sessionHydrated && sessionRestored
  });
  const { pageTracking, interactionTracking, trackEvent } = tracking;

  useEffect(() => {
    pageTracking.trackPageEnter('word-learning');
    return () => {
      pageTracking.trackPageLeave('word-learning');
    };
  }, [pageTracking]);

  useEffect(() => {
    updateLearningSession({ module: 'word' });
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
    trackEvent('module_navigate', 'word', { direction, to: target.key });
    goTo(target.key);
  };

  const renderBody = () => {
    if (loading) {
      return (
        <div className="flex-1 p-3 flex flex-col justify-center items-center text-gray-500 text-sm">
          加载词汇数据中...
        </div>
      );
    }

    if (error || !word) {
      return (
        <div className="flex-1 p-3 flex flex-col justify-center items-center text-red-500 text-sm text-center">
          无法加载词汇数据，请确认后端 API 是否已经运行。
        </div>
      );
    }

    return (
      <div className="flex-1 px-5 flex flex-col overflow-y-auto custom-scrollbar relative z-20">
        <div className="flex-1 space-y-4">
          {/* 复习模式下本来就在复习，不再提示「有到期复习」 */}
          {!learningSession.reviewMode && <ReviewReminder userId={userId} showInline={true} />}
          
          <div className="glass-panel p-6 rounded-3xl shadow-lg border border-white/60 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-100 rounded-full mix-blend-multiply filter blur-2xl opacity-50 pointer-events-none -mr-10 -mt-10"></div>
            <div className="relative z-10 space-y-6">
              <WordHero word={word} />
              <DefinitionBlock word={word} />
            </div>
          </div>
          {/* 前面步骤的内容折叠在这里，跳级进来的学习者也能补看 */}
          <RecapSection labels={["拆字"]}>
            <CharacterBreakdown word={word} />
          </RecapSection>
          <div className="h-6 w-full shrink-0"></div>
        </div>

        {/* 底部按钮区域保持为单大绿色 CONTINUE 按钮以符合原型图 */}
        <div className="pt-4 w-full z-30 px-5 pb-[calc(env(safe-area-inset-bottom)+1.5rem)]">
          <Button
              className="w-full h-12 rounded-xl border-none shadow-lg shadow-indigo-200 bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-indigo-300 text-white font-bold tracking-widest text-sm"
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
                className="h-9 px-3 bg-white/40 hover:bg-white/70 shadow-sm text-indigo-700 rounded-xl text-sm font-semibold"
                variant="ghost"
                disabled={!previous}
                onClick={() => handleNavigate('previous')}
              >
                ← {previous ? previous.label : '上一步'}
              </Button>
              <h1 className="text-xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-indigo-900 to-purple-800 tracking-tight leading-none pt-1">Word</h1>
              <Button
                className="h-9 px-3 bg-white/40 hover:bg-white/70 shadow-sm text-indigo-700 rounded-xl text-sm font-semibold"
                variant="ghost"
                disabled={!next}
                onClick={() => handleNavigate('next')}
              >
                {next ? next.label : '结束'} →
              </Button>
            </div>
            <div className="mt-3">
              <StepProgress current="word" entry={learningSession.entryModule} />
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
