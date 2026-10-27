import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from '@/components/ui/button';
import { ArrowLeft, ArrowRight, Search } from 'lucide-react';
import AudioPlayer from '@/components/AudioPlayer';
import { buildApiUrl } from '@/src/lib/apiClient';
import { afterWordRoute, useLearningSession } from '@/src/context/LearningSessionContext';

interface ConfusableWord {
  id: number;
  // 后端从 character 表拼出；拼不出时为 null，此时只能显示拼音
  hanzi: string | null;
  pinyin: string;
  definition: string;
}

interface ConfusablePair {
  id: number;
  word1: ConfusableWord;
  word2: ConfusableWord;
  reason: string;
  difference: string;
  examples: string;
  tips: string;
  difficulty_level: number;
}

/**
 * 易混淆词辨析学习页面
 */
export default function ConfusableWordsPage() {
  const router = useRouter();
  const { session } = useLearningSession();
  const [pairs, setPairs] = useState<ConfusablePair[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAnswer, setShowAnswer] = useState(false);
  // 从练习流程带入时（?pair=<id>&from=exercise）定位到对应组并提供“继续主线”出口
  const fromExercise = router.query.from === 'exercise';

  useEffect(() => {
    loadConfusablePairs();
  }, []);

  useEffect(() => {
    if (!router.isReady || pairs.length === 0) return;
    const pairId = Number(router.query.pair);
    if (!pairId) return;
    const idx = pairs.findIndex(p => p.id === pairId);
    if (idx >= 0) {
      setCurrentIndex(idx);
      setShowAnswer(false);
    }
  }, [router.isReady, router.query.pair, pairs]);

  const loadConfusablePairs = async () => {
    try {
      setLoading(true);
      const response = await fetch(buildApiUrl('/api/confusable/pairs?limit=20'));
      const data = await response.json();

      if (data.success) {
        setPairs(data.pairs);
      } else {
        setError(data.error || '加载失败');
      }
    } catch (err) {
      setError('网络错误，请检查后端服务');
      console.error('加载易混淆词失败:', err);
    } finally {
      setLoading(false);
    }
  };

  const currentPair = pairs[currentIndex];

  const handleNext = () => {
    if (currentIndex < pairs.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setShowAnswer(false);
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      setShowAnswer(false);
    }
  };

  const renderBody = () => {
    if (loading) {
      return (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          加载易混淆词数据中...
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
          <p className="text-sm text-red-500 mb-4">{error}</p>
          <Button
            onClick={loadConfusablePairs}
            className="h-11 px-8 rounded-2xl border-none text-white font-bold text-sm bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg hover:shadow-indigo-200 transition-all duration-300"
          >
            重试
          </Button>
        </div>
      );
    }

    if (!currentPair) {
      return (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          暂无易混淆词数据
        </div>
      );
    }

    return (
      <div className="flex-1 overflow-y-auto custom-scrollbar px-5 space-y-4 pb-4">
        {/* 词对比较 */}
        <div className="grid grid-cols-2 gap-3">
          {/* 词1 */}
          <div className="glass-panel rounded-2xl p-4 border-l-4 border-l-indigo-400">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-xl font-bold text-indigo-700">
                  {currentPair.word1.hanzi ?? currentPair.word1.pinyin}
                </h3>
                {currentPair.word1.hanzi && (
                  <p className="text-sm text-gray-500">{currentPair.word1.pinyin}</p>
                )}
              </div>
              <AudioPlayer
                text={currentPair.word1.hanzi ?? currentPair.word1.pinyin}
                language="zh-CN"
                buttonSize="sm"
              />
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">
              {currentPair.word1.definition}
            </p>
          </div>

          {/* 词2 */}
          <div className="glass-panel rounded-2xl p-4 border-l-4 border-l-emerald-400">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-xl font-bold text-emerald-700">
                  {currentPair.word2.hanzi ?? currentPair.word2.pinyin}
                </h3>
                {currentPair.word2.hanzi && (
                  <p className="text-sm text-gray-500">{currentPair.word2.pinyin}</p>
                )}
              </div>
              <AudioPlayer
                text={currentPair.word2.hanzi ?? currentPair.word2.pinyin}
                language="zh-CN"
                buttonSize="sm"
              />
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">
              {currentPair.word2.definition}
            </p>
          </div>
        </div>

        {/* 混淆原因 */}
        <div className="glass-panel rounded-2xl p-4 bg-amber-50/70">
          <h4 className="text-sm font-semibold text-amber-800 mb-1.5">💡 为什么易混淆？</h4>
          <p className="text-sm text-gray-700 leading-relaxed">{currentPair.reason}</p>
        </div>

        {/* 显示答案按钮 */}
        {!showAnswer && (
          <Button
            onClick={() => setShowAnswer(true)}
            className="w-full h-12 rounded-2xl border-none text-white font-bold tracking-wide text-sm bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg hover:shadow-indigo-200 transition-all duration-300"
          >
            <Search size={16} className="mr-2" /> 查看辨析详解
          </Button>
        )}

        {/* 详细辨析 */}
        {showAnswer && (
          <>
            <div className="glass-panel rounded-2xl p-4">
              <h4 className="text-sm font-semibold text-gray-800 mb-1.5">📖 详细区别</h4>
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                {currentPair.difference}
              </pre>
            </div>

            {currentPair.examples && (
              <div className="glass-panel rounded-2xl p-4 bg-emerald-50/70">
                <h4 className="text-sm font-semibold text-emerald-800 mb-1.5">📝 例句对比</h4>
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                  {currentPair.examples}
                </pre>
              </div>
            )}

            {currentPair.tips && (
              <div className="glass-panel rounded-2xl p-4 bg-indigo-50/70">
                <h4 className="text-sm font-semibold text-indigo-800 mb-1.5">💡 记忆技巧</h4>
                <p className="text-sm text-gray-700 leading-relaxed">{currentPair.tips}</p>
              </div>
            )}
          </>
        )}

        {/* 难度标识 */}
        <div className="text-center text-sm text-gray-400">
          难度等级: {'⭐'.repeat(currentPair.difficulty_level)}
        </div>
      </div>
    );
  };

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-[calc(env(safe-area-inset-bottom)+1rem)] flex flex-col relative z-20">
          {/* Header */}
          <div className="px-5 mb-4">
            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => window.history.back()}
                className="h-9 px-3 rounded-xl text-gray-600 bg-white/50 hover:bg-white/80 border border-white/60"
              >
                <ArrowLeft size={16} className="mr-1" /> 返回
              </Button>
              <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight">
                易混淆词辨析
              </h1>
              <div className="w-[72px]" />
            </div>
            {!loading && !error && pairs.length > 0 && (
              <p className="text-sm text-center text-indigo-500 font-medium mt-2">
                第 {currentIndex + 1} / {pairs.length} 组
              </p>
            )}
          </div>

          {/* Body */}
          {renderBody()}

          {/* Navigation */}
          {!loading && !error && pairs.length > 0 && (
            <div className="px-5 pt-3 space-y-2.5">
              {fromExercise && (
                <Button
                  onClick={() => router.push(afterWordRoute(session))}
                  className="w-full h-12 rounded-2xl border-none text-white font-bold tracking-wide text-sm bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg hover:shadow-indigo-200 transition-all duration-300"
                >
                  {session.reviewMode ? '完成辨析 · 继续复习' : '完成辨析 · 查看学习分析'} <ArrowRight size={16} className="ml-1.5" />
                </Button>
              )}
              <div className="flex gap-3">
                <Button
                  variant="ghost"
                  className="flex-1 h-11 rounded-2xl text-gray-700 bg-white/60 hover:bg-white/90 border border-white/60 disabled:opacity-40 transition-all"
                  onClick={handlePrevious}
                  disabled={currentIndex === 0}
                >
                  <ArrowLeft size={16} className="mr-1.5" /> 上一组
                </Button>
                <Button
                  variant="ghost"
                  className="flex-1 h-11 rounded-2xl text-gray-700 bg-white/60 hover:bg-white/90 border border-white/60 disabled:opacity-40 transition-all"
                  onClick={handleNext}
                  disabled={currentIndex === pairs.length - 1}
                >
                  下一组 <ArrowRight size={16} className="ml-1.5" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
