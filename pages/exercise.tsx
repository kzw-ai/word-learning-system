import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { fetchWordExercises } from '@/src/lib/apiClient';
import { authenticatedGet } from '@/src/lib/authClient';
import type { ExerciseQuestionPayload } from '@/src/lib/types';
import { useLearningContext } from '@/src/context/LearningContext';
import { afterWordRoute, reviewedToday, todayReviewKey, useLearningSession } from '@/src/context/LearningSessionContext';
import { isSingleCharacter, useLearningNavigation, resolveModuleLabel } from '@/src/hooks/useLearningNavigation';
import { useWordData } from '@/hooks/useWordData';
import ReviewReminder from '@/components/ReviewReminder';
import AudioPlayer from '@/components/AudioPlayer';
import StepProgress from '@/components/learning/StepProgress';
import { completeSentence, parseFillHint } from '@/src/lib/fillHint';

const DEFAULT_WORD_ID = 1;
const DEFAULT_WORD_NAME = '发生';

type ExerciseType = ExerciseQuestionPayload['type'];
type ExerciseQuestion = ExerciseQuestionPayload;

/**
 * 归一化作答后再比对：去首尾空白、全角转半角、英文统一小写。
 * 只吸收输入法差异，不放宽正确性判定。
 */
const normaliseAnswer = (value: string): string =>
  value
    .trim()
    .replace(/[！-～]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/　/g, ' ')
    .toLowerCase();

const Exercise = () => {
  const router = useRouter();
  const isReviewMode = router.query.mode === 'review';
  const isTestMode = router.query.mode === 'test';
  const { userId } = useLearningContext();
  const { session: learningSession, hydrated: sessionHydrated, restored: sessionRestored, updateSession: updateLearningSession } = useLearningSession();
  const initialWordId = learningSession.wordId ?? DEFAULT_WORD_ID;
  const initialWordLabel = learningSession.word ?? DEFAULT_WORD_NAME;
  const { previous, next, goTo } = useLearningNavigation('exercise');
  const [exerciseQuestions, setExerciseQuestions] = useState<ExerciseQuestion[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState<ExerciseQuestion | null>(null);
  // 填字题括号里的拼音提示，单独说明（见 src/lib/fillHint.ts）
  const fillHint = currentQuestion?.type === 'fill_word' ? parseFillHint(currentQuestion.question) : null;
  const [selectedOption, setSelectedOption] = useState('');
  const [fillInAnswer, setFillInAnswer] = useState(''); // 填空题答案
  const [showFeedback, setShowFeedback] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [sessionStartTime] = useState(new Date());
  const [wordId, setWordId] = useState(initialWordId);
  const [wordLabel, setWordLabel] = useState(initialWordLabel);
  const [wordDefinition, setWordDefinition] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Need the full word data to render the detailed feedback (character breakdown, pinyin, etc)
  const { word } = useWordData({ initialWordId: wordId });

  const {
    pageTracking,
    interactionTracking,
    exerciseTimer,
    trackEvent,
    trackExercise,
    endSession,
    updateConfig,
    sessionInfo
  } = useComprehensiveTracking({
    userId,
    wordId,
    moduleType: 'exercise',
    sessionType: 'exercise',
    // 本页的 wordId 要等题目加载完才跟上会话里的词：两者不一致时这个档位属于
    // 另一个词，不能记到当前会话上。跟上之后追踪器随 wordId 重建，带上档位
    initialLevel: learningSession.wordId === wordId ? learningSession.vksLevel ?? undefined : undefined,
    recommendationId: learningSession.wordId === wordId ? learningSession.recommendationId ?? undefined : undefined,
    // wordId 首帧是默认词（会话状态还没读出），题目加载完才是真正要练的词。
    // 提前建追踪器会先给默认词写一条 0 秒的幽灵会话
    ready: sessionHydrated && sessionRestored && exerciseQuestions.length > 0
  });
  const { trackPageEnter, trackPageLeave } = pageTracking;
  const { trackButtonClick, trackSelectionChange, trackAudioPlay } = interactionTracking;
  const {
    startTimer,
    submitAnswer,
    recordHesitation,
    hesitationCount,
    startTime: questionStartTime
  } = exerciseTimer;

  // 只采纳最近一次请求的结果：较早发出的请求晚返回时，不能用它覆盖当前的词
  const loadRequestRef = useRef(0);

  const loadExercises = useCallback(async (targetWordId: number, overrideLabel?: string | null) => {
    const requestId = ++loadRequestRef.current;
    setLoading(true);
    setError(null);

    try {
      const data = await fetchWordExercises(targetWordId, { limit: 5, options: 4 });
      if (requestId !== loadRequestRef.current) return;
      const normalizedQuestions: ExerciseQuestion[] = data.questions;

      if (!normalizedQuestions.length) {
        throw new Error('No exercises came back for this word');
      }

      setWordId(data.wordId);
      const effectiveWordLabel = overrideLabel ?? data.word ?? DEFAULT_WORD_NAME;
      setWordLabel(effectiveWordLabel);
      setWordDefinition(data.definition ?? '');
      setExerciseQuestions(normalizedQuestions);
      setQuestionIndex(0);
      setCurrentQuestion(normalizedQuestions[0]);
      setSelectedOption('');
      setFillInAnswer(''); // 重置填空答案
      setShowFeedback(false);
      setIsCorrect(false);
      updateConfig({ wordId: data.wordId });
      updateLearningSession({ wordId: data.wordId, word: effectiveWordLabel, module: 'exercise' });

      trackEvent('exercise_data_loaded', 'exercise', {
        wordId: data.wordId,
        questionCount: normalizedQuestions.length
      });
    } catch (err) {
      if (requestId !== loadRequestRef.current) return;
      const message = err instanceof Error ? err.message : 'Failed to load the exercises';
      trackEvent('exercise_load_failed', 'exercise', {
        wordId: targetWordId,
        error: message
      });

      // 不要回退到默认词：那样会把会话的词覆盖成「发生」，用户前几个模块
      // 学的是 A，练习记录却记在 B 头上。如实报错，让用户重试或离开。
      setExerciseQuestions([]);
      setCurrentQuestion(null);
      setError(message || 'Failed to load the exercises');
    } finally {
      if (requestId === loadRequestRef.current) {
        setLoading(false);
      }
    }
  }, [trackEvent, updateConfig, updateLearningSession]);

  const desiredWordId = useMemo(() => learningSession.wordId ?? DEFAULT_WORD_ID, [learningSession.wordId]);
  const desiredWordLabel = useMemo(() => learningSession.word ?? DEFAULT_WORD_NAME, [learningSession.word]);

  useEffect(() => {
    // 等会话从 localStorage 恢复后再加载：恢复前 desiredWordId 是默认词 1，
    // 提前请求会先拿到「发生」并写回会话
    if (!sessionHydrated) return;
    setWordLabel(desiredWordLabel);
    if (desiredWordId !== wordId || exerciseQuestions.length === 0) {
      loadExercises(desiredWordId, desiredWordLabel);
    }
  }, [sessionHydrated, desiredWordId, desiredWordLabel, wordId, exerciseQuestions.length, loadExercises]);

  useEffect(() => {
    updateConfig({ userId });
  }, [updateConfig, userId]);

  useEffect(() => {
    if (!exerciseQuestions.length) {
      return;
    }

    trackPageEnter('exercise');
    trackEvent('exercise_session_start', 'exercise', {
      wordId,
      word: wordLabel,
      totalQuestions: exerciseQuestions.length,
      startTime: sessionStartTime.toISOString()
    });

    return () => {
      trackPageLeave('exercise');
    };
  }, [exerciseQuestions.length, trackEvent, trackPageEnter, trackPageLeave, sessionStartTime, wordId, wordLabel]);

  useEffect(() => {
    if (!exerciseQuestions.length) {
      return;
    }

    const nextQuestion = exerciseQuestions[questionIndex];
    if (!nextQuestion) {
      return;
    }

    setCurrentQuestion(nextQuestion);
    setSelectedOption('');
    setFillInAnswer(''); // 重置填空答案
    setShowFeedback(false);
    setIsCorrect(false);
    startTimer();

    trackEvent('question_display', 'exercise', {
      questionId: nextQuestion.id,
      questionType: nextQuestion.type,
      questionIndex: questionIndex + 1,
      totalQuestions: exerciseQuestions.length
    });
  }, [exerciseQuestions, questionIndex, startTimer, trackEvent]);

  // 发音由 AudioPlayer 负责，这里只记录埋点
  const playAudio = (id: string) => {
    trackAudioPlay(id, 'exercise-audio');
    trackEvent('audio_play', id, {
      questionId: currentQuestion?.id,
      questionType: currentQuestion?.type,
      audioType: id
    });
  };

  const handleOptionChange = (value: string) => {
    if (!currentQuestion) {
      return;
    }

    if (selectedOption && selectedOption !== value) {
      const nextHesitation = hesitationCount + 1;
      recordHesitation();
      trackEvent('answer_change', 'option-change', {
        questionId: currentQuestion.id,
        from: selectedOption,
        to: value,
        hesitationCount: nextHesitation
      });
    }

    trackSelectionChange('exercise-option', selectedOption, value);
    setSelectedOption(value);
  };

  const handleSubmit = async () => {
    if (!currentQuestion || !questionStartTime) {
      return;
    }

    // 检查用户是否已作答
    const hasAnswer = currentQuestion.type === 'fill_word' ? fillInAnswer.trim() : selectedOption;
    if (!hasAnswer) {
      return;
    }

    trackButtonClick('submit-button', 'CHECK', {
      questionId: currentQuestion.id
    });

    submitAnswer();
    const endTime = new Date();
    const currentHesitations = hesitationCount;
    
    // 根据题目类型判断答案是否正确
    let correct = false;
    let userAnswer = '';
    
    if (currentQuestion.type === 'fill_word') {
      userAnswer = fillInAnswer.trim();
      // 填空题：严格相等比对。此前用双向子串匹配，正确答案「改变」时只写「改」、
      // 正确答案 'happen; occur' 时只输入 'a' 都会判对，正确率被系统性高估。
      correct = normaliseAnswer(userAnswer) === normaliseAnswer(currentQuestion.correctAnswer);
    } else {
      userAnswer = selectedOption;
      correct = selectedOption === currentQuestion.correctAnswer;
    }

    setIsCorrect(correct);
    setShowFeedback(true);

    const confidenceLevel = currentHesitations === 0 ? 5 : Math.max(1, 5 - currentHesitations);

    await trackExercise({
      questionId: currentQuestion.id,
      questionType: currentQuestion.type,
      questionContent: currentQuestion.question,
      userAnswer: userAnswer,
      correctAnswer: currentQuestion.correctAnswer,
      isCorrect: correct,
      startTime: questionStartTime,
      endTime,
      hesitationCount: currentHesitations,
      confidenceLevel
    });

    const responseTime = (endTime.getTime() - questionStartTime.getTime()) / 1000;

    trackEvent('exercise_submit', 'submit-button', {
      questionId: currentQuestion.id,
      questionType: currentQuestion.type,
      isCorrect: correct,
      responseTime,
      hesitationCount: currentHesitations,
      selectedAnswer: userAnswer,
      correctAnswer: currentQuestion.correctAnswer
    });
  };

  const handleContinue = async () => {
    trackButtonClick('continue-button', 'CONTINUE', {
      questionIndex: questionIndex + 1,
      totalQuestions: exerciseQuestions.length
    });

    if (questionIndex < exerciseQuestions.length - 1) {
      trackEvent('next_question', 'continue-button', {
        completedQuestionIndex: questionIndex + 1,
        remainingQuestions: exerciseQuestions.length - questionIndex - 1
      });
      setQuestionIndex(questionIndex + 1);
      return;
    }

    trackEvent('exercise_complete', 'exercise-end', {
      totalQuestions: exerciseQuestions.length,
      totalTime: Date.now() - sessionStartTime.getTime(),
      sessionId: sessionInfo?.sessionId
    });

    // 主线收尾环节：若本词存在易混淆词，先进入辨析再看学习分析。
    // 必须在 endSession 之前查询并埋点：endSession 会发出最后一批事件并把追踪器
    // 标记为已结束，之后再 trackEvent 的事件不会再被发送。
    let confusablePairId: number | null = null;
    let confusableAttempted = false;
    try {
      // 带上身份：后端只在两个词分别掌握到一定程度、这一对还没练过关时才带出（论文 2.2.4）
      const resp = await authenticatedGet(`/api/confusable/for-word/${wordId}`);
      const result = await resp.json();
      if (result.success && result.pair_id) {
        confusablePairId = result.pair_id;
        confusableAttempted = result.attempted === true;
        trackEvent('confusable_step', 'exercise-end', { wordId, pairId: result.pair_id });
      }
    } catch {
      // 查询失败不阻塞主流程
    }

    await endSession(true);

    // 复习模式下这个词的练习做完了：今天的复习列表不再显示它（作答万一没记下，也不会一直重复同一个词）。
    // 只在做完时记，点开始复习时不记：中途退出的词还要留在列表里
    if (learningSession.reviewMode) {
      updateLearningSession({
        reviewedWordIds: [...reviewedToday(learningSession).filter(id => id !== wordId), wordId],
        reviewDate: todayReviewKey()
      });
    }

    if (confusablePairId) {
      // 以前做过这一对的辨析题、没全对才再带出：辨析页直接展开讲解
      router.push(`/confusable-words?pair=${confusablePairId}&from=exercise${confusableAttempted ? '&revisit=1' : ''}`);
      return;
    }

    // 复习模式先回复习列表：练习的 next 恒为 dashboard，不能交给它
    if (learningSession.reviewMode) {
      router.push(afterWordRoute(learningSession));
    } else if (next) {
      goTo(next.key);
    } else {
      router.push(afterWordRoute(learningSession));
    }
  };

  const handleRetry = () => {
    trackButtonClick('retry-button', 'Reload');
    // 用会话里的目标词：加载失败时本地 wordId 没有更新，可能还是初始值 1
    loadExercises(desiredWordId, desiredWordLabel);
  };

  const handleLeave = () => {
    trackButtonClick('leave-button', 'Back to dashboard');
    router.push(afterWordRoute(learningSession));
  };

  const getQuestionTypeTitle = (type: ExerciseType) => {
    switch (type) {
      case 'definition':
        return 'Meaning';
      case 'collocation':
        return 'Collocation';
      case 'choose_word':
        return 'Easily confused words';
      case 'fill_word':
        return 'Fill in the character';
      default:
        return 'Practice';
    }
  };

  if (loading) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-gray-50">
        <div className="w-full max-w-[430px] h-[100dvh] modern-gradient-bg flex items-center justify-center">
          <p className="text-base text-gray-600">Loading the exercises…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-gray-50">
        <div className="w-full max-w-[430px] h-[100dvh] modern-gradient-bg flex flex-col items-center justify-center space-y-4 px-5 pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] text-center">
        <p className="text-red-600">❌ {error}</p>
        <div className="flex gap-3">
          <Button onClick={handleRetry}>Reload</Button>
          <Button variant="outline" onClick={handleLeave}>{learningSession.reviewMode ? 'Back to reviews' : 'Back to dashboard'}</Button>
        </div>
        </div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-gray-50">
        <div className="w-full max-w-[430px] h-[100dvh] modern-gradient-bg flex flex-col items-center justify-center space-y-3 px-5 text-center">
          <p className="text-base text-gray-600">No exercises available</p>
          <div className="flex gap-3">
            <Button onClick={handleRetry}>Try again</Button>
            <Button variant="outline" onClick={handleLeave}>{learningSession.reviewMode ? 'Back to reviews' : 'Back to dashboard'}</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        {/* Content */}
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-6 flex flex-col relative z-20">
          <div className="px-5 mb-3">
            <div className="flex justify-between items-center mb-4">
              <Button
                variant="ghost"
                size="sm"
                disabled={!previous}
                className="h-9 px-3 bg-transparent hover:bg-white/20 text-indigo-900 rounded-xl text-sm font-semibold shadow-none border border-transparent"
                onClick={() => {
                  if (!previous) return;
                  trackEvent('nav_previous', 'navigation', { targetModule: previous.key });
                  goTo(previous.key);
                }}
              >
                ← {previous ? previous.label : 'Back'}
              </Button>
              <h1 className="text-xl font-extrabold text-gray-800 tracking-tight pt-1 leading-none">
                {isTestMode ? 'Test' : (isReviewMode ? 'Review' : 'Practice')}
              </h1>
              <Button
                variant="ghost"
                size="sm"
                disabled={!next && !learningSession.reviewMode}
                className="h-9 px-2 bg-transparent hover:bg-white/20 text-indigo-900 rounded-lg text-sm shadow-none border border-transparent"
                onClick={() => {
                  // 复习模式下这个出口回复习列表，否则会绕过剩下的到期词
                  if (learningSession.reviewMode) {
                    trackEvent('nav_next', 'navigation', { targetModule: 'today-review' });
                    router.push(afterWordRoute(learningSession));
                    return;
                  }
                  if (!next) return;
                  trackEvent('nav_next', 'navigation', { targetModule: next.key });
                  goTo(next.key);
                }}
              >
                {learningSession.reviewMode ? 'Reviews' : (next ? next.label : 'Finish')} →
              </Button>
            </div>
            <div className="mt-3">
              <StepProgress current="exercise" entry={learningSession.entryModule} skipCharacter={isSingleCharacter(word)} />
            </div>
          </div>
          
          <div className="flex-1 px-5 flex flex-col justify-between overflow-y-auto custom-scrollbar relative z-20">
                <div className="space-y-3">
                  {/* 复习模式下本来就在复习，不再提示「有到期复习」 */}
                  {!learningSession.reviewMode && <ReviewReminder userId={userId} showInline={true} />}
                  
                {/* Title and Audio play */}
                <div>
                  <div className="flex items-baseline justify-between gap-3 mb-3">
                    <h2 className="text-xl font-extrabold text-gray-900 leading-snug tracking-wide">
                      {currentQuestion.type === 'definition' ?
                        'Choose the word that matches the meaning.' :
                        currentQuestion.type === 'collocation' ? 'Choose the word that fits the blank.' :
                        currentQuestion.type === 'choose_word' ? 'Choose the right word.' :
                        'Type the missing character.'
                      }
                    </h2>
                    <span className="text-sm font-semibold text-indigo-600 shrink-0" aria-label={`Question ${questionIndex + 1} of ${exerciseQuestions.length}`}>
                      {questionIndex + 1} / {exerciseQuestions.length}
                    </span>
                  </div>
                  <div className="mb-6 flex gap-2 items-center">
                    <p className="text-lg font-bold text-gray-800">{fillHint ? fillHint.stem : currentQuestion.question}</p>
                    {currentQuestion.type === 'definition' && (
                      <AudioPlayer
                        text={currentQuestion.question}
                        language="en-US"
                        buttonSize="sm"
                        onPlay={() => playAudio('question')}
                      />
                    )}
                  </div>
                  {/* 括号里的字母是答案那个字的拼音提示（还能填别的字时才给），单独说明，学习者才看得懂 */}
                  {fillHint?.hint && (
                    <p className="-mt-3 mb-5 text-base text-gray-600">
                      Hint: the pinyin {fillHint.initialOnly ? 'starts with' : 'is'}{' '}
                      <span className="font-semibold text-indigo-700">“{fillHint.hint}”</span>
                    </p>
                  )}
                </div>

                {/* Option / Input Area */}
                {currentQuestion.type === 'fill_word' ? (
                  <div className="flex flex-col items-center">
                    {/* 直接输入答案。原先的手写板没有识别能力，写完还要在浏览器弹窗里
                        再打一遍字；可用系统输入法（含手写输入）作答 */}
                    <div className="relative w-full max-w-[260px]">
                      <input
                        type="text"
                        value={fillInAnswer}
                        onChange={(e) => setFillInAnswer(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && fillInAnswer.trim() && !showFeedback) handleSubmit();
                        }}
                        disabled={showFeedback}
                        autoComplete="off"
                        aria-label="Type the missing character"
                        placeholder="Type here"
                        data-fill-input
                        className={`w-full h-16 text-center text-3xl font-bold rounded-2xl border-2 outline-none transition-colors placeholder:text-base placeholder:font-normal placeholder:text-gray-400 ${
                          showFeedback
                            ? isCorrect ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : 'border-red-500 bg-red-50 text-red-800'
                            : 'border-indigo-200 bg-white/80 text-gray-900 focus:border-indigo-500'
                        }`}
                      />
                      {showFeedback && (
                        <span className={`absolute top-1/2 -translate-y-1/2 right-4 text-xl font-bold ${isCorrect ? 'text-emerald-700' : 'text-red-700'}`} aria-hidden="true">
                          {isCorrect ? '✓' : '✗'}
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  // Multiple Choice Selection
                  <div className="space-y-3 mt-2">
                    {currentQuestion.options.map((option, index) => {
                      let btnClass = "w-full text-left min-h-[48px] py-3.5 pl-5 pr-14 rounded-[18px] transition-all duration-300 flex items-center justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ";
                      const isSelected = selectedOption === option;
                      
                      if (showFeedback) {
                        if (option === currentQuestion.correctAnswer) {
                          btnClass += "bg-emerald-700 border-none shadow-[0_4px_14px_0_rgba(4,120,87,0.35)] z-10 text-white font-bold";
                        } else if (isSelected) {
                          btnClass += "bg-rose-50 border-rose-300 shadow-sm text-rose-900 border font-bold";
                        } else {
                          btnClass += "glass-card text-gray-700 border-white/40 border font-bold";
                        }
                      } else {
                        btnClass += isSelected 
                          ? "bg-indigo-50 border-indigo-300 shadow-md ring-1 ring-indigo-200 z-10 text-indigo-900 border font-bold" 
                          : "glass-card hover:-translate-y-0.5 text-gray-700 border-white/40 border font-bold";
                      }
                      
                      const letter = String.fromCharCode(65 + index);
                      // Custom rendering if the option is the Chinese Word (like '发生') vs english options
                      const isHanziOption = /[\u4e00-\u9fa5]/.test(option);

                      const isCorrectOption = option === currentQuestion.correctAnswer;

                      return (
                        <div key={index} className="relative">
                          <button
                            disabled={showFeedback}
                            onClick={() => handleOptionChange(option)}
                            className={btnClass}
                          >
                            <span className="text-base leading-snug break-words flex items-center">
                              <span className={`mr-3 ${showFeedback && isCorrectOption ? 'text-white' : 'text-indigo-600'}`}>{letter}.</span>
                              <span>{option}</span>
                            </span>
                            {showFeedback && (isCorrectOption || isSelected) && (
                              <span className="text-lg font-bold" aria-label={isCorrectOption ? 'Correct answer' : 'Your answer'}>
                                {isCorrectOption ? '✓' : '✗'}
                              </span>
                            )}
                          </button>
                          {/* 与选项按钮并列而非嵌套：<button> 里不能再放 <button> */}
                          {isHanziOption && !showFeedback && (
                            <div className="absolute right-3 top-1/2 -translate-y-1/2 z-20">
                              <AudioPlayer
                                text={option}
                                language="zh-CN"
                                buttonSize="sm"
                                onPlay={() => playAudio(`option-${index}`)}
                              />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                
                {/* 统一的大画幅知识点嵌入式反馈面板 */}
                {showFeedback && (
                    <div className={`mt-5 px-5 py-5 -mx-5 border-t animate-in fade-in slide-in-from-bottom-2 duration-300 ${isCorrect ? 'bg-[#def6cd] border-[#baecbc]' : 'bg-[#ffe4e6] border-[#fbbabf]'}`}>
                       
                       <div className="flex items-center gap-2 mb-3">
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center ${isCorrect ? 'bg-emerald-700' : 'bg-red-600'}`}>
                            <span className="text-white text-lg font-bold">{isCorrect ? '✓' : '✗'}</span>
                          </div>
                          <span className={`font-extrabold text-[18px] tracking-wide ${isCorrect ? 'text-emerald-700' : 'text-red-700'}`}>
                             {isCorrect ? 'Excellent!' : 'Incorrect'}
                          </span>
                       </div>
                       
                       {!isCorrect && (
                          <div className="text-red-700 font-extrabold text-[14px] mb-3">
                             Correct answer: {currentQuestion.type === 'fill_word'
                               ? currentQuestion.correctAnswer
                               : `${String.fromCharCode(65 + currentQuestion.options.indexOf(currentQuestion.correctAnswer))}. ${currentQuestion.correctAnswer}`}
                          </div>
                       )}

                       {/* 内嵌知识点（取当前词的真实例句/搭配） */}
                       {word && (
                         <div className="mb-6">
                           {fillHint ? (
                              // 填字题：显示刚填完的这一句（不是学习页上那句例句），再给这个词的拼音和释义
                              <>
                                 <p className="text-[14px] font-bold text-gray-800 leading-snug mb-1.5">
                                   {completeSentence(fillHint.stem, currentQuestion.correctAnswer)}
                                 </p>
                                 <p className="text-base font-medium text-gray-700 leading-snug">
                                   <span className="mr-2 text-indigo-700">{wordLabel}</span>{word.pinyin}
                                   <span className="text-gray-500"> · {wordDefinition}</span>
                                 </p>
                              </>
                           ) : currentQuestion.type === 'choose_word' && word.examples?.[0] ? (
                              <>
                                 <p className="text-[14px] font-bold text-gray-800 leading-snug mb-1.5">
                                   {word.examples[0].sentence}
                                 </p>
                                 {word.examples[0].pinyin && (
                                   <p className="text-base font-medium text-gray-700 leading-snug tracking-wider mb-1.5">
                                     {word.examples[0].pinyin}
                                   </p>
                                 )}
                                 {word.examples[0].translation && (
                                   <p className="text-base font-normal text-gray-500 leading-snug">
                                     {word.examples[0].translation}
                                   </p>
                                 )}
                              </>
                           ) : currentQuestion.type === 'collocation' && word.collocations?.[0] ? (
                              <p className="text-[14px] font-bold text-gray-800 leading-relaxed tracking-wide">
                                 {word.collocations[0].collocation} {word.collocations[0].translation}
                              </p>
                           ) : (
                             <p className="text-[14px] font-bold text-gray-800 leading-relaxed tracking-wide">
                               <span className="mr-2 text-indigo-700">{wordLabel}</span> {word.pinyin} <br/>
                               <span className="text-base font-medium text-gray-600 mt-1 inline-block">{wordDefinition}</span>
                             </p>
                           )}
                         </div>
                       )}

                       {/* 将原本外部底部的CONTINUE按钮嵌入到面板深处 */}
                       <Button 
                         onClick={handleContinue}
                         className={`w-full h-[48px] rounded-[14px] border-none font-extrabold tracking-widest text-[14px] transition-all duration-300 text-white shadow-xl mb-[calc(env(safe-area-inset-bottom)+1.5rem)] ${
                            isCorrect ? 'bg-emerald-700 hover:bg-emerald-800 shadow-emerald-700/30' : 'bg-red-600 hover:bg-red-700 shadow-red-600/30'
                         }`}
                       >
                         CONTINUE
                       </Button>
                    </div>
                )}
              </div>
              
              {/* Spacer to guarantee scroll reaching the bottom properly */}
              <div className="h-6 w-full shrink-0"></div>


              {/* 仅在未反馈时才在底部显示唯一的SUBMIT类提交按钮 */}
              {!showFeedback && (
                <div className="pt-2 w-full z-30 px-5 pb-[calc(env(safe-area-inset-bottom)+1.5rem)]">
                  <Button 
                    onClick={handleSubmit}
                    disabled={currentQuestion.type === 'fill_word' ? !fillInAnswer.trim() : !selectedOption}
                    className="w-full h-[48px] rounded-xl border-none shadow-lg shadow-indigo-200 bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-indigo-300 disabled:from-gray-300 disabled:to-gray-300 disabled:shadow-none text-white font-bold tracking-widest text-[14px] transition-all duration-300"
                  >
                    CHECK
                  </Button>
                </div>
              )}
            </div>

            {/* Decorative blurs */}
            <div className="absolute top-1/4 -right-12 w-48 h-48 bg-indigo-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>
            <div className="absolute bottom-1/4 -left-12 w-48 h-48 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>

        </div>
      </div>
    </div>
  );
};

export default Exercise;
