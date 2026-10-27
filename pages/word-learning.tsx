import React, { useEffect, useState } from 'react';
import { Button } from "@/components/ui/button";
import { Battery, Signal, Wifi, Volume2 } from 'lucide-react';
import { useWordData } from '@/hooks/useWordData';
import { useLearningSession } from '@/src/context/LearningSessionContext';
import { useLearningNavigation, resolveModuleLabel } from '@/src/hooks/useLearningNavigation';
import { useLearningContext } from '@/src/context/LearningContext';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import ReviewReminder from '@/components/ReviewReminder';
import AudioPlayer from '@/components/AudioPlayer';
import CollocationText from '@/components/CollocationText';

export default function Component() {
  const { session: learningSession, hydrated: sessionHydrated, updateSession: updateLearningSession } = useLearningSession();
  const { userId } = useLearningContext();
  const { word, loading, error } = useWordData({ initialWordId: learningSession.wordId ?? undefined });
  const { previous, next, goTo } = useLearningNavigation('word');
  const [audioPlaying, setAudioPlaying] = useState<string | null>(null);

  const tracking = useComprehensiveTracking({
    userId,
    wordId: learningSession.wordId ?? 1,
    moduleType: 'word',
    sessionType: 'learning',
    initialLevel: learningSession.vksLevel ?? undefined,
    ready: sessionHydrated
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

  const mainExample = word?.examples?.[0];
  const collocations = word?.collocations ?? [];

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
          
          <div className="glass-panel p-6 rounded-3xl shadow-lg border border-white/60 text-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-100 rounded-full mix-blend-multiply filter blur-2xl opacity-50 pointer-events-none -mr-10 -mt-10"></div>
            
            <div className="flex flex-col items-center mb-2">
              <h2 className="text-[54px] font-extrabold text-gray-900 leading-none mb-2 mt-2">{word.hanzi}</h2>
              <div className="flex items-center gap-2 bg-indigo-50/80 px-4 py-1.5 rounded-full mb-2 z-10">
                <span className="text-sm font-medium text-indigo-700 tracking-widest">{word.pinyin}</span>
                <AudioPlayer 
                  text={word.hanzi} 
                  language="zh-CN"
                  buttonSize="sm"
                />
              </div>
            </div>

            <div className="mt-6 space-y-4 relative z-10 text-left">
              {/* Word Definition Block */}
              {word.definition && (
                <div className="glass-card p-5 rounded-2xl border border-white/40 mt-4">
                  <p className="text-lg text-gray-700 font-medium leading-relaxed">
                     {word.definition}
                  </p>
                </div>
              )}

              {/* Collocations Block */}
              {collocations.length > 0 && (
                <div className="glass-card p-5 rounded-2xl border border-white/40 space-y-4 mt-4">
                  {collocations.map((col, index) => {
                    return (
                    <div key={index} className="flex justify-between items-center group">
                      <div className="flex-1 pr-4">
                        <div className="flex items-center gap-1.5 text-lg font-semibold text-gray-800 mb-1 flex-wrap">
                          <CollocationText text={col.collocation} target={word.hanzi || word.pinyin} />
                        </div>
                        <p className="text-base font-normal text-gray-500 mt-0.5">{col.translation}</p>
                      </div>
                      <AudioPlayer 
                        text={col.collocation.replace(/\uff08[^\uff09]*\uff09/g, '')} 
                        audioUrl={col.audio}
                        language="zh-CN"
                        buttonSize="sm"
                      />
                    </div>
                  )})}
                </div>
              )}

               {/* Example Sentences Block */}
               {mainExample && (
                <div className="glass-card p-5 rounded-2xl border border-white/40 space-y-5 mt-4">
                    <div className="group flex flex-col relative">
                      <div className="flex justify-between items-start">
                        <p className="text-lg font-semibold text-gray-800 leading-relaxed pr-8">
                          {mainExample.sentence}
                        </p>
                        <div className="absolute top-0 right-0">
                          <AudioPlayer 
                            text={mainExample.sentence} 
                            audioUrl={mainExample.audio}
                            language="zh-CN"
                            buttonSize="sm"
                          />
                        </div>
                      </div>
                      {mainExample.pinyin && (
                        <p className="text-base text-indigo-600/80 mt-2 font-medium tracking-wide leading-relaxed">
                          {mainExample.pinyin}
                        </p>
                      )}
                      <p className="text-base text-gray-600 mt-2 leading-relaxed">
                        {mainExample.translation}
                      </p>
                    </div>
                </div>
              )}
            </div>
          </div>
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
            <p className="text-sm text-indigo-700 mt-2 font-medium ml-1">
              当前模块：{resolveModuleLabel('word')}
            </p>
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
