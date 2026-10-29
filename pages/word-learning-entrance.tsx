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

  const activeModuleLabel = useMemo(() => {
    if (!learningSession.module) {
      return null;
    }
    const key = learningSession.module.toLowerCase();
    return moduleRouteMap[key]?.label ?? learningSession.module;
  }, [learningSession.module]);

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
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-4 flex flex-col relative z-20">
          <div className="px-5 mb-4">
              <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight">Word Learning</h1>
              {/* 显示用户名或访客名；内部 user_id 对学习者没有意义 */}
              {displayName && (
                <p className="text-sm text-gray-500 mt-1 font-medium">
                  {displayName}
                  {isGuest && (
                    <>
                      {' · Guest · '}
                      <button
                        type="button"
                        onClick={() => router.push('/register')}
                        className="text-indigo-600 underline underline-offset-2"
                      >
                        Sign up to continue on other devices
                      </button>
                    </>
                  )}
                </p>
              )}
              <div className="text-sm text-gray-500 mt-3 space-y-1.5 bg-white/40 p-3 rounded-xl border border-white/60">
                <div className="flex justify-between items-center">
                  {wordsStudied !== null && <span>Words studied: {wordsStudied}</span>}
                  {learningSession.word && (
                    <span className="text-indigo-600 font-semibold">{activeModuleLabel || 'Practice'} · {learningSession.word}</span>
                  )}
                </div>
                {recommendationMessage && (
                  <p className="text-emerald-600 font-semibold mt-1.5">
                    💡 {recommendationMessage}
                  </p>
                )}
              </div>
              <div className="mt-4 flex gap-3">
                <Button
                  size="sm"
                  onClick={() => router.push('/learning-dashboard')}
                  className="flex-1 bg-white/60 text-indigo-700 hover:bg-white/80 text-sm h-11 rounded-xl shadow-sm border border-white/50 font-semibold"
                >
                  Dashboard
                </Button>
                <Button
                  size="sm"
                  onClick={() => router.push('/today-review')}
                  className="flex-1 bg-white/60 text-rose-600 hover:bg-white/80 text-sm h-11 rounded-xl shadow-sm border border-white/50 font-semibold"
                >
                  Today’s review
                </Button>
              </div>
            </div>
            
            <div className="flex-1 px-5 flex flex-col justify-between overflow-y-auto custom-scrollbar relative z-20">
              {caughtUp ? (
                <div className="glass-panel p-5 rounded-2xl space-y-2">
                  <p className="text-lg font-bold text-gray-800 leading-snug">You’re all caught up 🎉</p>
                  <p className="text-base text-gray-500 font-medium">
                    {caughtUp.nextReviewAt
                      ? `Your next review is ${formatReviewTime(caughtUp.nextReviewAt)}.`
                      : 'There are no new words to learn right now.'}
                  </p>
                </div>
              ) : (
              <div className="space-y-4">
                  <div className="glass-panel p-5 rounded-2xl">
                    <p className="text-lg font-bold text-gray-800 mb-2 leading-snug">How well do you know {targetWord?.word ?? DEFAULT_WORD_NAME}?</p>
                    <p className="text-base text-gray-500 font-medium">Choose the answer that fits you best.</p>
                  
                  <RadioGroup value={selectedOption} onValueChange={handleOptionChange} className="space-y-3 mt-4">
                    {learningOptions.map((option) => (
                      <div 
                        key={option.value} 
                        onClick={() => handleOptionChange(option.value)}
                        className={`flex items-center p-4 rounded-2xl cursor-pointer transition-all duration-300 border ${
                          selectedOption === option.value 
                            ? 'bg-indigo-50/80 border-indigo-200 shadow-md transform scale-[1.02]' 
                            : 'glass-card'
                        }`}
                      >
                        <RadioGroupItem 
                          value={option.value} 
                          id={option.value} 
                          className={`mr-4 shrink-0 border-gray-300 w-5 h-5 bg-white/70 ${selectedOption === option.value ? 'border-indigo-500 text-indigo-600' : ''}`}
                        />
                        <Label htmlFor={option.value} className={`text-base flex-1 cursor-pointer font-medium leading-relaxed ${
                          selectedOption === option.value ? 'text-indigo-900' : 'text-gray-700'
                        }`}>
                          {option.text}
                        </Label>
                      </div>
                    ))}
                  </RadioGroup>
                  
                  {recommendationError && (
                    <div className="p-3 text-sm text-rose-600 bg-rose-50/80 backdrop-blur-sm rounded-xl border border-rose-100">
                      {recommendationError}
                    </div>
                  )}
                </div>
                
                {/* 固定在屏幕底部：五个选项在小屏手机上一屏放不下，按钮也要一直看得到 */}
                <div className="sticky bottom-0 bg-gradient-to-t from-[#fbf3fa] via-[#f9f4fd]/95 to-transparent pt-6 -mx-5 px-5 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
                <Button
                  onClick={handleContinue}
                  disabled={!selectedOption || isSubmitting}
                  className="w-full relative group overflow-hidden bg-gradient-to-r from-indigo-500 to-purple-600 disabled:opacity-100 disabled:from-gray-300 disabled:to-gray-300 hover:shadow-lg disabled:shadow-none text-white py-6 text-base font-bold rounded-2xl border-none transition-all duration-300"
                >
                  <span className="relative z-10 tracking-wider text-glow">{isSubmitting ? 'LOADING…' : 'CONTINUE'}</span>
                  {!(!selectedOption || isSubmitting) && (
                    <div className="absolute inset-0 opacity-0 group-hover:opacity-20 bg-white transition-opacity duration-300"></div>
                  )}
                </Button>
                </div>
              </div>
              )}
            </div>

            {/* Decorative blurs */}
            <div className="absolute top-20 -right-10 w-40 h-40 bg-pink-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 pointer-events-none z-10"></div>
            <div className="absolute bottom-20 -left-10 w-40 h-40 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 pointer-events-none z-10"></div>

          </div>
        </div>
      </div>
  );
}

