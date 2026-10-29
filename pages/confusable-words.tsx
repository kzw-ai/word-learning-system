import React, { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from '@/components/ui/button';
import { ArrowLeft, ArrowRight, Search } from 'lucide-react';
import AudioPlayer from '@/components/AudioPlayer';
import { buildApiUrl } from '@/src/lib/apiClient';
import { authenticatedPost } from '@/src/lib/authClient';
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
  // 辨析题（论文 3.2.4）：句子来自学习材料里的例句，两个选项是这两个词
  questions?: ContrastQuestion[];
}

interface ContrastQuestion {
  stem: string;
  options: string[];
  correct_answer: string;
  // 英文讲解：为什么这句用这个词（学习资料制作第 6 步写、作者审核），答完显示
  explanation?: string;
  // 后端按题干、选项、答案算出的版本号；作答时带回去，题目改过时后端返回 409
  version: string;
}

type SaveState = 'saving' | 'saved' | 'failed' | 'stale';

// 每次作答一个编号，重试沿用同一个，后端据此去重
const newAttemptId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;

/**
 * 辨析题：每题选一次，选完即把题号和所选答案交给后端判分记录（不计入论文表 4.2 的复习次数）。
 * 后端按每道题最近一次作答是否都对决定之后还要不要带出这一对；保存失败的题可以重试。
 */
function ContrastQuiz({ pair }: { pair: ConfusablePair }) {
  const questions = pair.questions ?? [];
  const [picked, setPicked] = useState<Record<number, string>>({});
  const [saved, setSaved] = useState<Record<number, SaveState>>({});
  // 后端判分结果（对错与正确答案），以它为准；没返回之前先按本地答案显示
  const [judged, setJudged] = useState<Record<number, { ok: boolean; answer: string }>>({});
  const shownAt = useRef(Date.now());
  const elapsed = useRef<Record<number, number>>({});
  const attempts = useRef<Record<number, string>>({});

  useEffect(() => {
    setPicked({});
    setSaved({});
    setJudged({});
    elapsed.current = {};
    attempts.current = {};
    shownAt.current = Date.now();
  }, [pair.id]);

  if (questions.length === 0) return null;

  const save = async (index: number, option: string) => {
    setSaved(prev => ({ ...prev, [index]: 'saving' }));
    try {
      const resp = await authenticatedPost('/api/confusable/exercise/record', {
        pair_id: pair.id,
        question_index: index,
        question_version: questions[index].version,
        user_answer: option,
        response_time: elapsed.current[index],
        attempt_id: attempts.current[index],
      });
      const result = await resp.json().catch(() => null);
      if (resp.status === 409) {
        setSaved(prev => ({ ...prev, [index]: 'stale' }));
        return;
      }
      const ok = resp.ok && result?.success;
      setSaved(prev => ({ ...prev, [index]: ok ? 'saved' : 'failed' }));
      if (ok && typeof result.is_correct === 'boolean') {
        const answer = typeof result.correct_answer === 'string' ? result.correct_answer : questions[index].correct_answer;
        setJudged(prev => ({ ...prev, [index]: { ok: result.is_correct, answer } }));
      }
    } catch {
      setSaved(prev => ({ ...prev, [index]: 'failed' }));
    }
  };

  const choose = (index: number, option: string) => {
    if (picked[index]) return;
    setPicked(prev => ({ ...prev, [index]: option }));
    elapsed.current[index] = (Date.now() - shownAt.current) / 1000;
    attempts.current[index] = newAttemptId();
    shownAt.current = Date.now();
    void save(index, option);
  };

  const answerOf = (i: number) => judged[i]?.answer ?? questions[i].correct_answer;
  const isRight = (i: number) => judged[i]?.ok ?? picked[i] === answerOf(i);
  const allSaved = questions.every((_, i) => saved[i] === 'saved');
  const anyStale = questions.some((_, i) => saved[i] === 'stale');
  const correct = questions.filter((_, i) => isRight(i)).length;

  return (
    <div className="glass-panel rounded-2xl p-4">
      <h4 className="text-sm font-semibold text-gray-800 mb-1">✏️ Check yourself</h4>
      <p className="text-sm text-gray-500 mb-3">Choose the word that fits each sentence.</p>
      <div className="space-y-4">
        {questions.map((q, i) => {
          const choice = picked[i];
          return (
            <div key={i}>
              <p className="text-base text-gray-800 leading-relaxed mb-2">{q.stem}</p>
              <div className="grid grid-cols-2 gap-2">
                {q.options.map(option => {
                  const state = !choice || saved[i] === 'stale' ? 'idle'
                    : option === answerOf(i) ? 'right'
                    : option === choice ? 'wrong' : 'idle';
                  return (
                    <button
                      key={option}
                      type="button"
                      disabled={!!choice}
                      onClick={() => choose(i, option)}
                      className={`h-11 rounded-xl border-2 text-lg font-bold transition-colors ${
                        state === 'right' ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                        : state === 'wrong' ? 'border-red-400 bg-red-50 text-red-700'
                        : 'border-indigo-100 bg-white/80 text-gray-800 hover:border-indigo-300'
                      }`}
                    >
                      {option}
                    </button>
                  );
                })}
              </div>
              {choice && saved[i] !== 'stale' && (
                <p className={`text-sm mt-1.5 ${isRight(i) ? 'text-emerald-700' : 'text-red-600'}`}>
                  {isRight(i) ? 'Correct.' : `Not quite: the answer is ${answerOf(i)}.`}
                </p>
              )}
              {choice && saved[i] !== 'stale' && q.explanation && (
                <p className="text-sm mt-1 text-gray-600 leading-relaxed whitespace-pre-line">{q.explanation}</p>
              )}
              {saved[i] === 'stale' && (
                <p className="text-sm mt-1.5 text-amber-700">This question has been updated. Please reload the page.</p>
              )}
              {saved[i] === 'failed' && (
                <div className="flex items-center gap-2 mt-1.5">
                  <p className="text-sm text-amber-700">Your answer wasn&apos;t saved.</p>
                  <button
                    type="button"
                    onClick={() => save(i, choice)}
                    className="h-9 px-3 rounded-lg text-sm font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100"
                  >
                    Retry
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {allSaved && (
        <p className="text-sm font-semibold text-gray-700 mt-4">
          {correct} / {questions.length} correct
          {correct < questions.length ? '. This pair will come back next time you practise these words.' : '. Well done!'}
        </p>
      )}
      {anyStale && (
        <p className="text-sm font-semibold text-amber-700 mt-4">
          Some questions have been updated. Please reload the page to try them again.
        </p>
      )}
    </div>
  );
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
  // 以前做过这一对的辨析题、没全对才再带出（&revisit=1）：直接展开讲解
  const revisit = router.query.revisit === '1';

  useEffect(() => {
    if (router.isReady) loadConfusablePairs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, router.query.pair]);

  useEffect(() => {
    if (!router.isReady || pairs.length === 0) return;
    const pairId = Number(router.query.pair);
    if (!pairId) return;
    const idx = pairs.findIndex(p => p.id === pairId);
    if (idx >= 0) {
      setCurrentIndex(idx);
      setShowAnswer(revisit);
    }
  }, [router.isReady, router.query.pair, pairs, revisit]);

  // 只让最新一次加载更新页面：地址里的词对变了时，先发出的请求后返回也不能覆盖
  const loadSeq = useRef(0);

  const loadConfusablePairs = async () => {
    const seq = ++loadSeq.current;
    const stale = () => seq !== loadSeq.current;
    try {
      setLoading(true);
      const response = await fetch(buildApiUrl('/api/confusable/pairs?limit=20'));
      const data = await response.json();
      if (stale()) return;

      if (data.success) {
        // 从练习带入的那一对不一定在列表的前 20 对里：单独取来放在最前面
        const pairId = Number(router.query.pair);
        let list: ConfusablePair[] = data.pairs;
        if (pairId && !list.some(p => p.id === pairId)) {
          const resp = await fetch(buildApiUrl(`/api/confusable/pair/${pairId}`));
          const single = await resp.json().catch(() => null);
          if (stale()) return;
          if (!resp.ok || !single?.success) {
            // 要学的是这一对：加载不到就报错，不能拿列表里别的词对顶替
            setError('Could not load this pair of words.');
            return;
          }
          list = [single.pair, ...list];
        }
        setError(null);
        setPairs(list);
      } else {
        setError(data.error || 'Failed to load');
      }
    } catch (err) {
      if (stale()) return;
      setError('Network error. Please try again later.');
      console.error('加载易混淆词失败:', err);
    } finally {
      if (!stale()) setLoading(false);
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
          Loading easily confused words…
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
            Retry
          </Button>
        </div>
      );
    }

    if (!currentPair) {
      return (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          No easily confused words yet
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
          <h4 className="text-sm font-semibold text-amber-800 mb-1.5">💡 Why they get mixed up</h4>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{currentPair.reason}</p>
        </div>

        {/* 显示答案按钮 */}
        {!showAnswer && (
          <Button
            onClick={() => setShowAnswer(true)}
            className="w-full h-12 rounded-2xl border-none text-white font-bold tracking-wide text-sm bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg hover:shadow-indigo-200 transition-all duration-300"
          >
            <Search size={16} className="mr-2" /> See the full comparison
          </Button>
        )}

        {/* 详细辨析 */}
        {showAnswer && (
          <>
            <div className="glass-panel rounded-2xl p-4">
              <h4 className="text-sm font-semibold text-gray-800 mb-1.5">📖 The difference</h4>
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                {currentPair.difference}
              </pre>
            </div>

            {currentPair.examples && (
              <div className="glass-panel rounded-2xl p-4 bg-emerald-50/70">
                <h4 className="text-sm font-semibold text-emerald-800 mb-1.5">📝 Example sentences</h4>
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                  {currentPair.examples}
                </pre>
              </div>
            )}

            {currentPair.tips && (
              <div className="glass-panel rounded-2xl p-4 bg-indigo-50/70">
                <h4 className="text-sm font-semibold text-indigo-800 mb-1.5">💡 Memory tip</h4>
                <p className="text-sm text-gray-700 leading-relaxed">{currentPair.tips}</p>
              </div>
            )}

            <ContrastQuiz pair={currentPair} />
          </>
        )}

        {/* 难度标识 */}
        <div className="text-center text-sm text-gray-400">
          Difficulty: {'⭐'.repeat(currentPair.difficulty_level)}
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
                <ArrowLeft size={16} className="mr-1" /> Back
              </Button>
              <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight">
                Easily confused words
              </h1>
              <div className="w-[72px]" />
            </div>
            {!loading && !error && pairs.length > 0 && (
              <p className="text-sm text-center text-indigo-500 font-medium mt-2">
                Pair {currentIndex + 1} of {pairs.length}
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
                  {session.reviewMode ? 'Done · continue reviewing' : 'Done · see my progress'} <ArrowRight size={16} className="ml-1.5" />
                </Button>
              )}
              <div className="flex gap-3">
                <Button
                  variant="ghost"
                  className="flex-1 h-11 rounded-2xl text-gray-700 bg-white/60 hover:bg-white/90 border border-white/60 disabled:opacity-40 transition-all"
                  onClick={handlePrevious}
                  disabled={currentIndex === 0}
                >
                  <ArrowLeft size={16} className="mr-1.5" /> Previous pair
                </Button>
                <Button
                  variant="ghost"
                  className="flex-1 h-11 rounded-2xl text-gray-700 bg-white/60 hover:bg-white/90 border border-white/60 disabled:opacity-40 transition-all"
                  onClick={handleNext}
                  disabled={currentIndex === pairs.length - 1}
                >
                  Next pair <ArrowRight size={16} className="ml-1.5" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
