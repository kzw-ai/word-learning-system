import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Battery, Signal, Wifi, Volume2 } from "lucide-react";
import { useWordData } from "@/hooks/useWordData";
import { useLearningSession } from "@/src/context/LearningSessionContext";
import { useLearningNavigation } from "@/src/hooks/useLearningNavigation";
import { useLearningContext } from "@/src/context/LearningContext";
import { useComprehensiveTracking } from "@/hooks/useTimeTracking";
import AudioPlayer from "@/components/AudioPlayer";
import CollocationText from "@/components/CollocationText";

export default function Component() {
  const { session: learningSession, hydrated: sessionHydrated, updateSession: updateLearningSession } =
    useLearningSession();
  const { word, loading, error } = useWordData({
    initialWordId: learningSession.wordId ?? undefined,
  });
  const { previous, next, goTo } = useLearningNavigation("character");
  const { userId } = useLearningContext();

  const tracking = useComprehensiveTracking({
    userId,
    wordId: learningSession.wordId ?? 1,
    moduleType: 'character',
    sessionType: 'learning',
    initialLevel: learningSession.vksLevel ?? undefined,
    ready: sessionHydrated
  });
  const { pageTracking, interactionTracking, trackEvent } = tracking;

  useEffect(() => {
    pageTracking.trackPageEnter('character-learning');
    return () => {
      pageTracking.trackPageLeave('character-learning');
    };
  }, [pageTracking]);

  useEffect(() => {
    updateLearningSession({ module: "character" });
  }, [updateLearningSession]);

  useEffect(() => {
    if (word) {
      updateLearningSession({ wordId: word.id, word: word.hanzi });
    }
  }, [word, updateLearningSession]);

  const handleNavigate = (direction: "previous" | "next") => {
    const target = direction === "previous" ? previous : next;
    if (!target) return;
    interactionTracking.trackButtonClick(`navigate-${direction}`, target.label);
    trackEvent('module_navigate', 'character', { direction, to: target.key });
    goTo(target.key);
  };

  const renderBody = () => {
    if (loading) {
      return (
        <div className="flex-1 p-3 flex flex-col justify-center items-center text-gray-500 text-sm">
          加载字形数据中...
        </div>
      );
    }

    if (error || !word) {
      return (
        <div className="flex-1 p-3 flex flex-col justify-center items-center text-red-500 text-sm text-center">
          无法加载字形信息，请检查 API 服务。
        </div>
      );
    }

    const characters = word.characters ?? [];

    return (
      <div className="flex-1 px-5 flex flex-col justify-between overflow-y-auto custom-scrollbar relative z-20">
        <div className="space-y-4">
          <div className="glass-panel p-6 rounded-3xl shadow-lg border border-white/60 text-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-100 rounded-full mix-blend-multiply filter blur-2xl opacity-50 pointer-events-none -mr-10 -mt-10"></div>

            <div className="flex flex-col items-center mb-2">
              <h2 className="text-[54px] font-extrabold text-gray-900 leading-none mb-2">
                {word.hanzi}
              </h2>
              <div className="flex items-center gap-2 bg-indigo-50/80 px-4 py-1.5 rounded-full">
                <span className="text-sm font-medium text-indigo-700 tracking-widest">
                  {word.pinyin}
                </span>
                <AudioPlayer 
                  text={word.hanzi} 
                  language="zh-CN"
                  buttonSize="sm"
                />
              </div>
            </div>

            <div className="mt-6 space-y-4 relative z-10 text-left">
              {characters.length === 0 && (
                <p className="text-sm text-gray-500 text-center">
                  暂无字形数据。
                </p>
              )}
              {/* Character Block */}
              {characters.map((item, index) => (
                <div
                  key={`${item.character}-${index}`}
                  className="flex-1 flex items-center p-3 rounded-2xl border border-white/40 glass-card"
                >
                    <span className="font-extrabold text-lg text-gray-800 shrink-0 w-8">
                      {item.character}
                    </span>
                    <span className="text-sm font-semibold text-indigo-500 shrink-0 w-12 text-left">
                      {item.pinyin}
                    </span>
                    <p className="text-sm text-gray-700 font-medium px-2 flex-1 leading-relaxed break-words">
                      {item.definition}
                    </p>
                    <AudioPlayer 
                      text={item.character} 
                      language="zh-CN"
                      buttonSize="sm"
                    />
                </div>
              ))}

              {/* Word Definition Block */}
              {word.definition && (
                <div className="glass-card p-5 rounded-2xl border border-white/40 mt-4 bg-white/40 shadow-sm">
                  <p className="text-lg text-gray-800 font-medium leading-relaxed text-center">
                     {word.definition}
                  </p>
                </div>
              )}

              {/* Collocations Block */}
              {word.collocations && word.collocations.length > 0 && (
                <div className="glass-card p-4 rounded-2xl border border-white/40 space-y-3 mt-4">
                  {word.collocations.map((col, index) => {
                    return (
                    <div key={index} className="flex justify-between items-center group">
                      <div className="flex-1 pr-4">
                        <div className="flex items-center gap-1.5 text-lg font-semibold text-gray-800 mb-1 flex-wrap">
                          <CollocationText text={col.collocation} target={word.hanzi || word.pinyin} />
                        </div>
                        <p className="text-base font-normal text-gray-600 mt-1">{col.translation}</p>
                      </div>
                      <AudioPlayer 
                        text={col.collocation.replace(/\uff08[^\uff09]*\uff09/g, '')} 
                        language="zh-CN"
                        buttonSize="sm"
                      />
                    </div>
                  )})}
                </div>
              )}

               {/* Example Sentences Block */}
               {word.examples && word.examples.length > 0 && (
                <div className="glass-card p-5 rounded-2xl border border-white/40 space-y-5 mt-4">
                  {word.examples.map((ex, index) => (
                    <div key={index} className="group flex flex-col relative">
                      <div className="flex justify-between items-start">
                        <p className="text-lg font-semibold text-gray-800 leading-relaxed pr-8">
                          {ex.sentence}
                        </p>
                        <div className="absolute top-0 right-0">
                          <AudioPlayer 
                            text={ex.sentence} 
                            language="zh-CN"
                            buttonSize="sm"
                          />
                        </div>
                      </div>
                      {ex.pinyin && (
                        <p className="text-base text-indigo-600/80 mt-2 font-medium tracking-wide leading-relaxed">
                          {ex.pinyin}
                        </p>
                      )}
                      <p className="text-base text-gray-600 mt-2 leading-relaxed">
                        {ex.translation}
                      </p>
                    </div>
                  ))}
                </div>
              )}
              {/* Spacer to guarantee scroll reaching the bottom properly */}
              <div className="h-6 w-full shrink-0"></div>
            </div>
          </div>
        </div>

        {/* 底部 CONTINUE 按钮，与全站主色（indigo-purple 渐变）统一 */}
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
                variant="ghost"
                size="sm"
                disabled={!previous}
                className="h-9 px-3 bg-white/40 hover:bg-white/70 shadow-sm text-indigo-700 rounded-xl text-sm font-semibold"
                onClick={() => handleNavigate("previous")}
              >
                ← {previous ? previous.label : "上一步"}
              </Button>
              <h1 className="text-xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-indigo-900 to-purple-800 tracking-tight leading-none pt-1">
                Character
              </h1>
              <Button
                variant="ghost"
                size="sm"
                disabled={!next}
                className="h-9 px-3 bg-white/40 hover:bg-white/70 shadow-sm text-indigo-700 rounded-xl text-sm font-semibold"
                onClick={() => handleNavigate("next")}
              >
                {next ? next.label : "结束"} →
              </Button>
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
