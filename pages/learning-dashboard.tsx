import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { buildApiUrl } from "@/src/lib/apiClient";
import { sendRecommendationFeedback } from "@/src/lib/authClient";
import { useLearningContext } from '@/src/context/LearningContext';
import { useLearningSession } from '@/src/context/LearningSessionContext';
import { formatReviewTime } from '@/src/lib/reviewTime';
import { 
  TrendingUp, BookOpen, 
  Clock, Target, Award, ChevronRight 
} from 'lucide-react';

interface Recommendation {
  type: string;
  priority: string;
  // 暂时没有任务（all_caught_up）时为空
  word_id: number | null;
  word?: string;
  reason: string;
  recommended_module: string | null;
  confidence: number;
  estimated_time: number;
  recommendationId?: number | null;
  next_review_at?: string | null;
}

interface DashboardData {
  overallProgress: {
    totalWords: number;
    /** 四级词（有词频档位）一共几个、学过几个；和首页的进度条同一口径（一到三级的易混淆词不算） */
    hsk4Words?: number;
    hsk4Studied?: number;
    studiedWords: number;
    masteredWords: number;
    averageMastery: number;
  };
  todayStats: {
    studyTimeMinutes: number;
    wordsReviewed: number;
    exercisesCompleted: number;
    averageAccuracy: number;
  };
  recommendations: Recommendation[];
  dueReviews: number;
  strengths: string[];
  weaknesses: string[];
}

const LearningDashboard = () => {
  const router = useRouter();
  const { userId } = useLearningContext();
  const { updateSession } = useLearningSession();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);

  useEffect(() => {
    if (!userId) return;
    fetchDashboardData();
    fetchRecommendation();
  }, [userId]);

  const fetchDashboardData = async () => {
    try {
      const response = await fetch(buildApiUrl(`/api/analytics/user/${userId}/dashboard`));
      const result = await response.json();

      if (response.ok && result.success) {
        setDashboardData(result.data);
      }
    } catch (err) {
      console.error('加载Dashboard数据失败:', err);
    }
  };

  const fetchRecommendation = async () => {
    try {
      setLoading(true);
      const response = await fetch(buildApiUrl(`/api/adaptive/recommendation/${userId}`));
      const result = await response.json();

      if (response.ok && result.success) {
        setRecommendation(result.data);
      } else {
        setError(result.error || 'The service is unavailable');
      }
    } catch (err) {
      setError('Couldn’t connect. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const startRecommendedLearning = () => {
    if (!recommendation?.word_id) return;

    // 新词先做 VKS 自评（论文表 4.2 按自评档位定复习次数，入口模块也由档位决定），
    // 入口页沿用这条推荐的词，不另取推荐；采纳由入口页在选完档位后上报
    if (recommendation.type === 'new_learning') {
      updateSession({
        wordId: recommendation.word_id,
        word: recommendation.word,
        module: null,
        entryModule: null,
        vksLevel: undefined,
        recommendationId: recommendation.recommendationId ?? null,
        reviewMode: null,
        lastUpdated: new Date().toISOString()
      });
      router.push(`/word-learning-entrance?wordId=${recommendation.word_id}`);
      return;
    }

    sendRecommendationFeedback(userId, recommendation.recommendationId, true,
      `${recommendation.recommended_module}:${recommendation.word_id}`);

    updateSession({
      wordId: recommendation.word_id,
      word: recommendation.word,
      module: recommendation.recommended_module,
      entryModule: recommendation.recommended_module,
      vksLevel: undefined,
      recommendationId: recommendation.recommendationId ?? null,
      reviewMode: null,
      // 用户主动开始：即使内容与原来相同也要刷新时间戳
      lastUpdated: new Date().toISOString()
    });

    const moduleRoutes: Record<string, string> = {
      character: '/character-learning',
      word: '/word-learning',
      collocation: '/collocation-learning',
      sentence: '/sentence-learning',
      exercise: '/exercise',
      urgent_review: '/exercise',
      scheduled_review: '/exercise',
      new_learning: '/word-learning'
    };

    const route = moduleRoutes[recommendation.recommended_module ?? ''] || moduleRoutes[recommendation.type] || '/word-learning';
    router.push(route);
  };

  const getModuleLabel = (module: string) => {
    const labels: Record<string, string> = {
      character: 'Characters',
      word: 'Word',
      collocation: 'Collocations',
      sentence: 'Sentences',
      exercise: 'Practice',
      urgent_review: 'Urgent review',
      scheduled_review: 'Scheduled review',
      new_learning: 'New word'
    };
    return labels[module] || module;
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      urgent_review: 'Urgent review',
      scheduled_review: 'Review due',
      new_learning: 'New word',
      all_caught_up: 'All caught up',
      system_default: 'Suggested'
    };
    return labels[type] || type;
  };

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    return `about ${minutes} min`;
  };

  const overall = dashboardData?.overallProgress;
  const hsk4Words = overall?.hsk4Words ?? overall?.totalWords ?? 0;
  const hsk4Studied = overall?.hsk4Studied ?? overall?.studiedWords ?? 0;

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-4 flex flex-col relative z-20">
          {/* Header */}
          <div className="px-5 mb-4 shrink-0">
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight flex items-center">
              <TrendingUp className="mr-2 text-indigo-500" size={24} />
              Dashboard
            </h1>
          </div>

          {/* Main Content */}
          <div className="flex-1 overflow-y-auto px-5 pb-4 space-y-4 custom-scrollbar scroll-fade">
            {loading && !recommendation && (
              <div className="glass-card mb-4 rounded-3xl p-8 text-center shadow-lg border border-white/40">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mx-auto mb-3"></div>
                <p className="text-base text-gray-500 font-medium tracking-wide">Loading your progress…</p>
              </div>
            )}

            {error && !recommendation && (
              <div className="glass-card mb-4 rounded-3xl p-5 bg-rose-50/50 border border-rose-200/60 shadow-lg">
                <p className="text-base text-rose-700 font-medium text-center">{error}</p>
              </div>
            )}

            {/* 暂时没有任务：不显示开始按钮 */}
            {recommendation && !recommendation.word_id && (
              <div className="glass-card mb-4 rounded-[28px] p-5 shadow-xl border border-white/60 space-y-2">
                <h2 className="text-lg font-bold text-gray-800">You’re all caught up</h2>
                <p className="text-base text-gray-600 font-medium">
                  {recommendation.next_review_at
                    ? `Your next review is ${formatReviewTime(recommendation.next_review_at)}.`
                    : 'There are no new words to learn right now.'}
                </p>
              </div>
            )}

            {/* 智能推荐卡片 */}
            {recommendation?.word_id && (
              <div className="glass-panel rounded-3xl p-5 short:p-4">
                {/* 一张卡说清三件事：学什么（右边的词）、为什么（左边的类型和理由）、从哪开始要多久（下面一行） */}
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="min-w-0">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-semibold bg-indigo-50 text-indigo-700 mb-2">
                      <Target size={14} aria-hidden="true" />
                      {getTypeLabel(recommendation.type)}
                    </span>
                    <p className="text-sm text-slate-600 font-medium leading-snug">{recommendation.reason}</p>
                  </div>
                  <div className="px-4 py-2.5 rounded-2xl bg-indigo-50 border border-indigo-100 shrink-0">
                    <span className="text-3xl font-extrabold text-slate-900 leading-none">{recommendation.word}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 py-2.5 px-3.5 rounded-xl bg-slate-50 border border-slate-200/60 text-sm text-slate-700 mb-4 short:mb-3">
                  <span className="flex items-center font-semibold">
                    <BookOpen size={15} className="mr-1.5 text-indigo-600" aria-hidden="true" />
                    {/* 新词先做 VKS 自评，从哪一步学由自评决定 */}
                    {recommendation.type === 'new_learning'
                      ? 'Self-check'
                      : getModuleLabel(recommendation.recommended_module || recommendation.type)}
                  </span>
                  <span className="text-slate-300" aria-hidden="true">|</span>
                  <span className="flex items-center font-medium">
                    <Clock size={15} className="mr-1.5 text-indigo-600" aria-hidden="true" />
                    {formatTime(recommendation.estimated_time)}
                  </span>
                </div>

                <Button
                  onClick={startRecommendedLearning}
                  className="w-full h-12 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 active:scale-[0.99] text-white text-base font-bold tracking-wide shadow-md shadow-indigo-500/20 border-none transition-all duration-200"
                >
                  Start now
                  <ChevronRight size={18} className="ml-1" aria-hidden="true" />
                </Button>
              </div>
            )}

            {/* 今日统计 */}
            {dashboardData && (
              <div className="glass-panel rounded-3xl p-5 short:p-4">
                <div className="flex items-center mb-4">
                  <Award className="mr-2 text-indigo-500" size={20} />
                  <h3 className="text-lg font-bold text-slate-900">Today</h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-center p-3 bg-slate-50 rounded-2xl border border-slate-200/60">
                    <div className="text-2xl short:text-xl font-extrabold text-slate-900 tabular-nums">
                      {dashboardData.todayStats.wordsReviewed}
                    </div>
                    <div className="text-sm text-slate-600 mt-0.5 font-medium">Words studied</div>
                  </div>
                  <div className="text-center p-3 bg-slate-50 rounded-2xl border border-slate-200/60">
                    <div className="text-2xl short:text-xl font-extrabold text-slate-900 tabular-nums">
                      {dashboardData.todayStats.exercisesCompleted}
                    </div>
                    <div className="text-sm text-slate-600 mt-0.5 font-medium">Exercises</div>
                  </div>
                  <div className="text-center p-3 bg-slate-50 rounded-2xl border border-slate-200/60">
                    <div className="text-2xl short:text-xl font-extrabold text-slate-900 tabular-nums">
                      {dashboardData.todayStats.studyTimeMinutes}
                    </div>
                    <div className="text-sm text-slate-600 mt-0.5 font-medium">Minutes</div>
                  </div>
                  <div className="text-center p-3 bg-slate-50 rounded-2xl border border-slate-200/60">
                    <div className="text-2xl short:text-xl font-extrabold text-slate-900 tabular-nums">
                      {(dashboardData.todayStats.averageAccuracy * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-slate-600 mt-0.5 font-medium">Accuracy</div>
                  </div>
                </div>
              </div>
            )}

            {/* 整体进度 */}
            {dashboardData && (
              <div className="glass-panel rounded-3xl p-5 short:p-4">
                <div className="flex items-center mb-4">
                  <TrendingUp className="mr-2 text-indigo-500" size={20} />
                  <h3 className="text-lg font-bold text-slate-900">Overall</h3>
                </div>
                <div className="space-y-4">
                  <div>
                    {/* 按四级词算，和首页一致；旧接口没有这两个字段时退回全部词 */}
                    <div className="flex justify-between items-end mb-2">
                      <span className="text-base text-slate-600 font-medium">HSK 4 words learned</span>
                      <span className="text-lg font-bold text-gray-800">
                        {hsk4Studied} <span className="text-sm text-slate-500 font-normal">/ {hsk4Words}</span>
                      </span>
                    </div>
                    <Progress 
                      value={hsk4Words ? (hsk4Studied / hsk4Words) * 100 : 0} 
                      className="h-2 bg-white/50 [&>div]:bg-gradient-to-r [&>div]:from-blue-400 [&>div]:to-indigo-500"
                    />
                  </div>
                  
                  <div>
                    <div className="flex justify-between items-end mb-2">
                      <span className="text-base text-slate-600 font-medium">Average mastery</span>
                      <span className="text-lg font-bold text-emerald-700">
                        {(dashboardData.overallProgress.averageMastery * 100).toFixed(1)}%
                      </span>
                    </div>
                    <Progress 
                      value={dashboardData.overallProgress.averageMastery * 100} 
                      className="h-2 bg-white/50 [&>div]:bg-gradient-to-r [&>div]:from-emerald-400 [&>div]:to-teal-500"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* 快捷操作 */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <button
                onClick={() => {
                  // 推荐显示着却去了别处：记为没有采纳
                  sendRecommendationFeedback(userId, recommendation?.recommendationId, false, 'today-review');
                  router.push('/today-review');
                }}
                className="glass-card flex flex-col items-center justify-center p-4 rounded-3xl text-slate-800 hover:text-indigo-700 relative overflow-hidden transition-all duration-300"
              >
                <div className="bg-indigo-50 text-indigo-500 p-3 rounded-2xl mb-3">
                  <Clock size={24} />
                </div>
                <span className="text-base font-bold">Today’s review</span>
                {dashboardData && dashboardData.dueReviews > 0 && (
                  <span className="absolute top-2.5 right-2.5 flex h-6 min-w-6 px-1.5 shrink-0 items-center justify-center rounded-full bg-rose-600 text-sm font-bold text-white shadow-sm ring-2 ring-white tabular-nums">
                    {dashboardData.dueReviews > 99 ? '99+' : dashboardData.dueReviews}
                  </span>
                )}
              </button>
              <button
                onClick={() => {
                  sendRecommendationFeedback(userId, recommendation?.recommendationId, false, 'word-learning-entrance');
                  router.push('/word-learning-entrance');
                }}
                className="glass-card flex flex-col items-center justify-center p-4 rounded-3xl text-slate-800 hover:text-indigo-700 transition-all duration-300"
              >
                <div className="bg-purple-50 text-purple-500 p-3 rounded-2xl mb-3">
                  <BookOpen size={24} />
                </div>
                <span className="text-base font-bold">Start learning</span>
              </button>
            </div>
          </div>

          {/* Bottom Actions */}
          <div className="px-5 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] shrink-0 pt-3">
            <Button
              variant="ghost"
              onClick={() => router.push('/')}
              className="w-full h-11 rounded-xl text-slate-600 hover:text-indigo-700 hover:bg-white/60 text-sm font-semibold transition-colors"
            >
              Back to home
            </Button>
          </div>
        </div>

        {/* Decorative blurs */}
        <div className="absolute top-1/3 -right-12 w-48 h-48 bg-indigo-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>
        <div className="absolute bottom-1/3 -left-12 w-48 h-48 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>
      </div>
    </div>
  );
};

export default LearningDashboard;
