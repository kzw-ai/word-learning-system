import React, { useState, useEffect, useMemo } from 'react';
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Battery, Signal, Wifi } from 'lucide-react';
import { useRouter } from 'next/router';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { buildApiUrl } from '@/src/lib/apiClient';
import { sendRecommendationFeedback } from '@/src/lib/authClient';
import { useLearningContext } from '@/src/context/LearningContext';
import { guestDisplayName, isGuestId, safeGetItem } from '@/src/lib/guestIdentity';
import { useLearningSession } from '@/src/context/LearningSessionContext';
import { formatReviewTime } from '@/src/lib/reviewTime';

const DEFAULT_WORD_ID = 1;
const DEFAULT_WORD_NAME = '发生';

const moduleRouteMap: Record<string, { path: string; label: string }> = {
  character: { path: '/character-learning', label: 'Characters' },
  word: { path: '/word-learning', label: 'Word' },
  word_learning: { path: '/word-learning', label: 'Word' },
  collocation: { path: '/collocation-learning', label: 'Collocations' },
  collocation_learning: { path: '/collocation-learning', label: 'Collocations' },
  sentence: { path: '/sentence-learning', label: 'Sentences' },
  sentence_learning: { path: '/sentence-learning', label: 'Sentences' },
  exercise: { path: '/exercise', label: 'Practice' },
  review: { path: '/exercise', label: 'Review' },
  urgent_review: { path: '/exercise', label: 'Urgent review' },
  scheduled_review: { path: '/exercise', label: 'Scheduled review' },
  explore_learning: { path: '/word-learning', label: 'Explore' },
  new_learning: { path: '/word-learning', label: 'New word' },
};

interface RecommendationResolution {
  path: string;
  label: string;
  moduleKey: string;
}

const resolveModuleRoute = (moduleName: string | undefined, fallbackPath: string, fallbackLabel: string): RecommendationResolution => {
  const normalized = (moduleName || '').toLowerCase();
  const match = moduleRouteMap[normalized];
  if (match) {
    return { path: match.path, label: match.label, moduleKey: normalized };
  }
  // 认不出模块名时按回退路径反查，不能一律记成 word（会话里的模块就和实际页面对不上）
  const fallbackKey = Object.keys(moduleRouteMap).find((key) => moduleRouteMap[key].path === fallbackPath);
  return { path: fallbackPath, label: fallbackLabel, moduleKey: fallbackKey ?? 'word' };
};

export default function Component() {
  const { session: learningSession, updateSession: updateLearningSession } = useLearningSession();

  const [selectedOption, setSelectedOption] = useState(learningSession.vksLevel ?? '');
  const [pageStartTime] = useState(new Date());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [recommendationMessage, setRecommendationMessage] = useState<string | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  // 本次要测评的目标词：由推荐引擎决定（挂载后加载，初始用默认词保证水合一致）
  const [targetWord, setTargetWord] = useState<{ id: number; word: string; recommendationId?: number } | null>(null);
  // 推荐引擎说暂时没有任务（新词学完、复习未到期）：不再拿默认词来问，显示下次复习时间（UTC 字符串，可能为空）
  const [caughtUp, setCaughtUp] = useState<{ nextReviewAt: string | null } | null>(null);
  // 推荐请求结束（拿到词、暂无任务或失败）以后才建学习会话：之前不知道问的是哪个词，会话会记到默认词上
  const [recommendationSettled, setRecommendationSettled] = useState(false);
  // 学过的词数（有学习进度的词）；看板接口给的，取不到时不显示
  const [wordsStudied, setWordsStudied] = useState<number | null>(null);
  const router = useRouter();
  const { userId, availableUsers } = useLearningContext();

  const currentUser = useMemo(() => availableUsers.find(user => user.userId === userId), [availableUsers, userId]);
  const isGuest = isGuestId(userId);
  // 登录用户显示用户名；访客显示由 ID 推出的固定名字
  const displayName = useMemo(() => {
    // 身份确定前（服务端渲染与客户端首帧）一律不显示，两边才一致，不会水合报错
    if (!userId) return null;
    if (currentUser?.username) return currentUser.username;
    if (isGuest) return guestDisplayName(userId);
    return safeGetItem('username');
  }, [currentUser, isGuest, userId]);

  const lastModuleLabel = useMemo(() => {
    const moduleKey = currentUser?.lastSession?.moduleType?.toLowerCase();
    if (!moduleKey) {
      return null;
    }
    return moduleRouteMap[moduleKey]?.label ?? currentUser?.lastSession?.moduleType;
  }, [currentUser]);

  const tracking = useComprehensiveTracking({
    userId,
    // 自评问的是哪个词就记哪个词；推荐没拿到、页面退回去问默认词时记默认词。暂无任务时不问，也不建会话
    wordId: targetWord?.id ?? DEFAULT_WORD_ID,
    moduleType: 'entrance',
    sessionType: 'learning',
    ready: recommendationSettled && !caughtUp
  });

  const { pageTracking, interactionTracking, trackEvent, updateConfig, endSession } = tracking;
  const { trackPageEnter, trackPageLeave, trackNavigation } = pageTracking;
  const { trackSelectionChange, trackButtonClick } = interactionTracking;

  // 自评是对页面上问的这个词的。只有会话里正是这个词时才预选它已有的档位；
  // 推荐的词晚到、换掉了页面上的词时，之前的选择作废，要重新选
  const askedWordId = targetWord?.id ?? DEFAULT_WORD_ID;
  useEffect(() => {
    setSelectedOption(learningSession.wordId === askedWordId ? learningSession.vksLevel ?? '' : '');
  }, [askedWordId, learningSession.wordId, learningSession.vksLevel]);

  // 从推荐引擎获取本次学习的目标词。从看板点「开始」学新词时，看板已经拿到推荐并写进会话，
  // 地址里带着 wordId：直接问这个词，不再请求一次（否则多一条推荐记录，采纳记到另一条上）
  const passedWordId = Number(router.query.wordId) || null;
  useEffect(() => {
    if (!userId || !router.isReady) return;
    if (passedWordId && learningSession.wordId === passedWordId && learningSession.word) {
      setTargetWord({ id: passedWordId, word: learningSession.word, recommendationId: learningSession.recommendationId ?? undefined });
      setRecommendationSettled(true);
      return;
    }
    let cancelled = false;
    fetch(buildApiUrl(`/api/adaptive/recommendation/${userId}`), { cache: 'no-cache' })
      .then(resp => resp.json())
      .then(result => {
        if (cancelled || !result.success || !result.data) return;
        const { word_id: wordId, word, recommendationId, type, next_review_at: nextReviewAt } = result.data;
        if (wordId && word) {
          setTargetWord({ id: wordId, word, recommendationId });
        } else if (type === 'all_caught_up') {
          setCaughtUp({ nextReviewAt: nextReviewAt ?? null });
        }
      })
      .catch(() => {
        /* 拉取失败时保持默认词，不阻塞流程 */
      })
      .finally(() => {
        if (!cancelled) setRecommendationSettled(true);
      });
    return () => {
      cancelled = true;
    };
    // 会话里的词只在进页时读一次：之后点「继续」写会话，不能因此重新取推荐
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, router.isReady, passedWordId]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    fetch(buildApiUrl(`/api/analytics/user/${userId}/dashboard`), { cache: 'no-cache' })
      .then(resp => resp.json())
      .then(result => {
        const studied = result?.data?.overallProgress?.studiedWords;
        if (!cancelled && result.success && typeof studied === 'number') setWordsStudied(studied);
      })
      .catch(() => {
        /* 取不到就不显示 */
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    updateConfig({ userId });
  }, [userId, updateConfig]);

  useEffect(() => {
    // 追踪器等推荐结果出来才建（见上），进页和「开始自评」要等它建好再记
    if (!recommendationSettled) return;
    trackPageEnter('word-learning-entrance');
    trackEvent('vks_test_start', 'entrance', {
      word: targetWord?.word ?? DEFAULT_WORD_NAME,
      startTime: pageStartTime.toISOString(),
      userId
    });

    return () => {
      trackPageLeave('word-learning-entrance');
    };
  }, [trackEvent, trackPageEnter, trackPageLeave, userId, pageStartTime, recommendationSettled]);

  const handleOptionChange = (value: string) => {
    trackSelectionChange('vks-level', selectedOption, value);

    if (selectedOption && selectedOption !== value) {
      trackEvent('option_change', 'vks-radio', {
        from: selectedOption,
        to: value,
        hesitation: true
      });
    }

    // 只改页面上的选择；点「继续」时连同词一起写进会话。此前选择时就写，
    // 会话里还是上一个词，档位就先记到了上一个词上
    setSelectedOption(value);
    setRecommendationMessage(null);
    setRecommendationError(null);
  };

  const learningOptions = [
    { value: 'A', module: 'character', text: 'I have never seen this word.', path: '/character-learning', label: 'Characters' },
    { value: 'B', module: 'word', text: "I don't know what it means.", path: '/word-learning', label: 'Word' },
    { value: 'C', module: 'collocation', text: "I know what it means, but not which words go with it.", path: '/collocation-learning', label: 'Collocations' },
    { value: 'D', module: 'sentence', text: "I know which words go with it, but I can't use it in a sentence yet.", path: '/sentence-learning', label: 'Sentences' },
    { value: 'E', module: 'exercise', text: 'I can use it in a sentence.', path: '/exercise', label: 'Practice' }
  ];

  const handleContinue = async () => {
    trackButtonClick('continue-button', 'CONTINUE', {
      selectedOption,
      timeToDecision: Date.now() - pageStartTime.getTime()
    });

    if (!selectedOption) {
      trackEvent('validation_error', 'continue-button', {
        error: 'no_option_selected'
      });
      alert('Please choose an answer first');
      return;
    }

    const selectedLearning = learningOptions.find(option => option.value === selectedOption);
    if (!selectedLearning) {
      alert('Something went wrong with your choice. Please try again.');
      return;
    }

    setIsSubmitting(true);
    setRecommendationError(null);

    // 学的是页面上问的那个词：进页时推荐引擎给的词，没拿到推荐时是默认词。
    // 入口模块由所选档位决定（与后端的 VKS→模块对照表相同），不再请求第二次推荐：
    // 第二次请求会让引擎另挑一个词，自评档位就记到了没问过的词上，还多一条对不上的推荐日志
    const resolvedWordId = targetWord?.id ?? DEFAULT_WORD_ID;
    const resolvedWord = targetWord?.word ?? DEFAULT_WORD_NAME;
    // 单字词（如「得」）拆不出字，字页和词页内容一样：选 A 的也从词页开始（档位仍记 A，复习次数不变）
    const singleChar = Array.from(resolvedWord).length === 1;
    const resolvedModule = singleChar && selectedLearning.module === 'character'
      ? resolveModuleRoute('word', '/word-learning', 'Word')
      : resolveModuleRoute(selectedLearning.module, selectedLearning.path, selectedLearning.label);
    const recommendationId = targetWord?.recommendationId ?? null;
    setRecommendationMessage(`Starting with ${resolvedModule.label} · ${resolvedWord}`);

    try {
      trackEvent('vks_test_complete', 'entrance', {
        selectedLevel: selectedOption,
        selectedPath: selectedLearning.path,
        resolvedPath: resolvedModule.path,
        resolvedModule: resolvedModule.moduleKey,
        recommendationId,
        decisionTime: Date.now() - pageStartTime.getTime(),
        totalTime: Date.now() - pageStartTime.getTime(),
        userId
      });

      updateConfig({ wordId: resolvedWordId, moduleType: resolvedModule.moduleKey });

      // 照推荐的词开始学了
      sendRecommendationFeedback(userId, recommendationId, true, `${resolvedModule.moduleKey}:${resolvedWordId}`);

      updateLearningSession({
        wordId: resolvedWordId,
        word: resolvedWord,
        module: resolvedModule.moduleKey,
        entryModule: resolvedModule.moduleKey,
        vksLevel: selectedOption,
        recommendationId,
        reviewMode: null,
        // 用户主动确认：即使内容与原来相同也要刷新时间戳，不能被稍后到的服务器旧状态覆盖
        lastUpdated: new Date().toISOString()
      });

      await endSession(true);
      trackNavigation('word-learning-entrance', resolvedModule.path);
      router.push(resolvedModule.path);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+0.75rem)] flex flex-col relative z-20">
          {/* 顶栏和学习页一样：左回看板，中间标题，右去复习 */}
          <div className="px-5 mb-3 short:mb-2 shrink-0">
            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                onClick={() => router.push('/learning-dashboard')}
                className="h-9 px-3 rounded-xl bg-white/80 hover:bg-white border border-slate-200/70 shadow-sm text-indigo-700 text-sm font-semibold"
              >
                ← Dashboard
              </Button>
              <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">Self-check</h1>
              <Button
                variant="ghost"
                onClick={() => router.push('/today-review')}
                className="h-9 px-3 rounded-xl bg-white/80 hover:bg-white border border-slate-200/70 shadow-sm text-indigo-700 text-sm font-semibold"
              >
                Review →
              </Button>
            </div>
            {/* 显示用户名或访客名；内部 user_id 对学习者没有意义 */}
            {displayName && (
              <p className="text-sm text-slate-600 mt-2 short:mt-1.5 text-center">
                {displayName}
                {isGuest && (
                  <>
                    {' · Guest · '}
                    <button
                      type="button"
                      onClick={() => router.push('/register')}
                      className="inline-block py-2 -my-2 text-indigo-700 font-semibold"
                    >
                      Sign up to save progress
                    </button>
                  </>
                )}
              </p>
            )}
            {/* 只在高屏上显示这一栏：手机上（包括大屏手机）放了它，自评的五个选项就要滚动才看得全 */}
            {(wordsStudied !== null || recommendationMessage) && (
              <div className="text-sm text-slate-600 mt-3 glass-card rounded-xl px-3 py-2 hidden tall:flex justify-between gap-3">
                {wordsStudied !== null && <span>Words studied: {wordsStudied}</span>}
                {recommendationMessage && <span className="text-emerald-700 font-semibold">{recommendationMessage}</span>}
              </div>
            )}
          </div>

          {/* 题目卡和按钮是一组，在剩下的高度里上下居中；放不下时这一块滚动 */}
          <div className="flex-1 min-h-0 px-5 overflow-y-auto custom-scrollbar scroll-fade flex flex-col">
            <div className="my-auto pb-[calc(env(safe-area-inset-bottom)+1rem)] short:pb-[calc(env(safe-area-inset-bottom)+0.75rem)]">
              {caughtUp ? (
                <div className="glass-panel p-5 rounded-3xl space-y-2">
                  <p className="text-lg font-bold text-slate-900 leading-snug">You’re all caught up</p>
                  <p className="text-base text-slate-600 font-medium">
                    {caughtUp.nextReviewAt
                      ? `Your next review is ${formatReviewTime(caughtUp.nextReviewAt)}.`
                      : 'There are no new words to learn right now.'}
                  </p>
                </div>
              ) : (
                <>
                  <div className="glass-panel p-5 short:p-3.5 rounded-3xl">
                    {/* 要自评的词单独放大，是这一页的主角 */}
                    <div className="flex items-center justify-between gap-3 pb-3.5 short:pb-2.5 mb-3.5 short:mb-2.5 border-b border-slate-100">
                      <div>
                        <p className="text-sm font-semibold text-indigo-700">New word</p>
                        <h2 className="text-base font-semibold text-slate-700 mt-0.5 leading-snug">How well do you know this word?</h2>
                      </div>
                      <div className="px-4 py-2 short:px-3 short:py-1.5 rounded-2xl bg-indigo-50 border border-indigo-100 shrink-0">
                        <span data-target-word className="text-3xl short:text-2xl font-extrabold text-slate-900 leading-none">
                          {targetWord?.word ?? DEFAULT_WORD_NAME}
                        </span>
                      </div>
                    </div>

                    {/* 1–5 对应认识程度由浅到深（论文表 4.2 的五个档位） */}
                    <RadioGroup value={selectedOption} onValueChange={handleOptionChange} className="gap-2 short:gap-1.5">
                      {learningOptions.map((option, index) => {
                        const active = selectedOption === option.value;
                        return (
                          <div
                            key={option.value}
                            onClick={() => handleOptionChange(option.value)}
                            className={`flex items-center gap-3 px-3.5 py-2.5 short:px-3 short:py-2 rounded-2xl cursor-pointer transition-colors border ${
                              active
                                ? 'bg-indigo-50 border-indigo-500 ring-1 ring-indigo-500/20'
                                : 'bg-white border-slate-200/80 hover:border-indigo-200'
                            }`}
                          >
                            <RadioGroupItem value={option.value} id={option.value} className="sr-only" />
                            <span
                              aria-hidden="true"
                              className={`w-7 h-7 rounded-full text-sm font-bold flex items-center justify-center shrink-0 transition-colors ${
                                active ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'
                              }`}
                            >
                              {index + 1}
                            </span>
                            <Label
                              htmlFor={option.value}
                              className={`text-base short:text-[15px] flex-1 cursor-pointer leading-snug ${
                                active ? 'text-indigo-950 font-semibold' : 'text-slate-700 font-medium'
                              }`}
                            >
                              {option.text}
                            </Label>
                          </div>
                        );
                      })}
                    </RadioGroup>

                    {recommendationError && (
                      <div className="mt-3 p-3 text-sm text-rose-700 bg-rose-50 rounded-xl border border-rose-100">
                        {recommendationError}
                      </div>
                    )}
                  </div>

                  <Button
                    onClick={handleContinue}
                    disabled={!selectedOption || isSubmitting}
                    className="w-full h-14 short:h-12 mt-4 short:mt-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 active:scale-[0.99] disabled:from-slate-200 disabled:to-slate-200 disabled:text-slate-500 disabled:opacity-100 shadow-md shadow-indigo-500/20 disabled:shadow-none text-white text-base font-bold tracking-wider rounded-2xl border-none transition-all duration-200"
                  >
                    {isSubmitting ? 'LOADING…' : 'CONTINUE'}
                  </Button>
                </>
              )}
            </div>
          </div>

            {/* Decorative blurs */}
            <div className="absolute top-20 -right-10 w-40 h-40 bg-violet-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 pointer-events-none z-10"></div>
            <div className="absolute bottom-20 -left-10 w-40 h-40 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 pointer-events-none z-10"></div>

          </div>
        </div>
      </div>
  );
}

