import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { buildApiUrl } from "@/src/lib/apiClient";
import { useLearningContext } from '@/src/context/LearningContext';
import { useLearningSession } from '@/src/context/LearningSessionContext';
import { 
  TrendingUp, BookOpen, 
  Clock, Target, Award, ChevronRight 
} from 'lucide-react';

interface Recommendation {
  type: string;
  priority: string;
  word_id: number;
  word: string;
  reason: string;
  recommended_module: string;
  confidence: number;
  estimated_time: number;
  recommendationId?: number;
}

interface DashboardData {
  overallProgress: {
    totalWords: number;
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
        setError(result.error || 'API服务未运行');
      }
    } catch (err) {
      setError('无法连接到API服务');
    } finally {
      setLoading(false);
    }
  };

  const startRecommendedLearning = () => {
    if (!recommendation) return;

    updateSession({
      wordId: recommendation.word_id,
      word: recommendation.word,
      module: recommendation.recommended_module,
      vksLevel: undefined,
      reviewMode: null
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

    const route = moduleRoutes[recommendation.recommended_module] || moduleRoutes[recommendation.type] || '/word-learning';
    router.push(route);
  };

  const getModuleLabel = (module: string) => {
    const labels: Record<string, string> = {
      character: '字学习',
      word: '词学习',
      collocation: '搭配学习',
      sentence: '例句学习',
      exercise: '练习',
      urgent_review: '紧急复习',
      scheduled_review: '计划复习',
      new_learning: '新词学习'
    };
    return labels[module] || module;
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      urgent_review: '🚨 紧急复习',
      scheduled_review: '📅 计划复习',
      new_learning: '✨ 新词学习',
      explore_learning: '🔍 探索学习',
      system_default: '📚 系统推荐'
    };
    return labels[type] || type;
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      high: 'bg-red-500',
      medium: 'bg-orange-500',
      low: 'bg-blue-500'
    };
    return colors[priority] || 'bg-gray-500';
  };

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    return `约 ${minutes} 分钟`;
  };

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-4 flex flex-col relative z-20">
          {/* Header */}
          <div className="px-5 mb-4 shrink-0">
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight flex items-center">
              <TrendingUp className="mr-2 text-indigo-500" size={24} />
              学习看板 Dashboard
            </h1>
          </div>

          {/* Main Content */}
          <div className="flex-1 overflow-y-auto px-5 space-y-4 custom-scrollbar">
            {loading && !recommendation && (
              <div className="glass-card mb-4 rounded-3xl p-8 text-center shadow-lg border border-white/40">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mx-auto mb-3"></div>
                <p className="text-base text-gray-500 font-medium tracking-wide">加载智能分析中...</p>
              </div>
            )}

            {error && !recommendation && (
              <div className="glass-card mb-4 rounded-3xl p-5 bg-rose-50/50 border border-rose-200/60 shadow-lg">
                <p className="text-base text-rose-600 font-medium text-center">❌ {error}</p>
              </div>
            )}

            {/* 智能推荐卡片 */}
            {recommendation && (
              <div className="glass-card mb-4 rounded-[28px] overflow-hidden shadow-xl border border-white/60 relative">
                <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-200/40 rounded-full mix-blend-multiply filter blur-2xl pointer-events-none -mr-10 -mt-10"></div>
                <div className="p-5 pb-4 bg-gradient-to-br from-white/40 to-white/10 border-b border-white/30 backdrop-blur-md relative z-10 flex items-center justify-between">
                  <h2 className="text-lg font-bold text-gray-800 flex items-center">
                    <Target className="mr-2 text-indigo-500" size={20} />
                    智能推荐
                  </h2>
                  <Badge className={`${getPriorityColor(recommendation.priority)} bg-opacity-90 shadow-sm border-none text-sm px-3 py-1`}>
                    {recommendation.priority === 'high' ? '高' : 
                     recommendation.priority === 'medium' ? '中' : '低'}优先级
                  </Badge>
                </div>
                <div className="p-5 space-y-4 relative z-10">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="text-sm text-indigo-600/80 mb-1 font-medium tracking-wider uppercase">
                        {getTypeLabel(recommendation.type)}
                      </div>
                      <h3 className="font-extrabold text-3xl text-gray-900 leading-none">{recommendation.word}</h3>
                    </div>
                  </div>
                  
                  <div className="p-3.5 bg-white/40 rounded-xl text-base text-gray-600 font-medium border border-white/50 leading-relaxed shadow-sm">
                    💡 {recommendation.reason}
                  </div>

                  <div className="grid grid-cols-2 gap-3 mt-2">
                    <div className="bg-white/30 p-3.5 rounded-xl border border-white/40 shadow-sm">
                      <div className="text-sm text-gray-500 mb-1 font-medium">推荐模块</div>
                      <div className="text-base font-bold text-gray-800 flex items-center">
                        <BookOpen size={16} className="mr-1.5 text-indigo-400" />
                        {getModuleLabel(recommendation.recommended_module || recommendation.type)}
                      </div>
                    </div>
                    <div className="bg-white/30 p-3.5 rounded-xl border border-white/40 shadow-sm">
                      <div className="text-sm text-gray-500 mb-1 font-medium">预计时间</div>
                      <div className="text-base font-bold text-gray-800 flex items-center">
                        <Clock size={16} className="mr-1.5 text-indigo-400" />
                        {formatTime(recommendation.estimated_time)}
                      </div>
                    </div>
                  </div>

                  <div className="mt-2 pt-3 border-t border-white/30">
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-gray-500 font-medium">推荐匹配度</span>
                      <span className="font-bold text-indigo-700">{(recommendation.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <Progress value={recommendation.confidence * 100} className="h-2 bg-white/50 [&>div]:bg-gradient-to-r [&>div]:from-indigo-400 [&>div]:to-purple-500" />
                  </div>

                  <Button
                    onClick={startRecommendedLearning}
                    className="w-full relative group overflow-hidden bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg text-white py-5 text-base font-bold rounded-2xl mt-4 border-none transition-all duration-300"
                  >
                    <span className="relative z-10 flex items-center tracking-wider text-glow">
                      立即开始
                      <ChevronRight size={18} className="ml-1" />
                    </span>
                    <div className="absolute inset-0 opacity-0 group-hover:opacity-20 bg-white transition-opacity duration-300"></div>
                  </Button>
                </div>
              </div>
            )}

            {/* 今日统计 */}
            {dashboardData && (
              <div className="glass-card mb-4 rounded-[28px] p-5 border border-white/40 shadow-sm">
                <div className="flex items-center mb-4">
                  <Award className="mr-2 text-indigo-500" size={20} />
                  <h3 className="text-lg font-bold text-gray-800">今日学习</h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-center p-4 bg-white/40 rounded-2xl border border-white/50 shadow-sm">
                    <div className="text-3xl font-bold text-indigo-600">
                      {dashboardData.todayStats.wordsReviewed}
                    </div>
                    <div className="text-sm text-gray-500 mt-1.5 font-medium">复习词汇</div>
                  </div>
                  <div className="text-center p-4 bg-white/40 rounded-2xl border border-white/50 shadow-sm">
                    <div className="text-3xl font-bold text-emerald-600">
                      {dashboardData.todayStats.exercisesCompleted}
                    </div>
                    <div className="text-sm text-gray-500 mt-1.5 font-medium">完成练习</div>
                  </div>
                  <div className="text-center p-4 bg-white/40 rounded-2xl border border-white/50 shadow-sm">
                    <div className="text-3xl font-bold text-purple-600">
                      {dashboardData.todayStats.studyTimeMinutes}
                    </div>
                    <div className="text-sm text-gray-500 mt-1.5 font-medium">学习分钟</div>
                  </div>
                  <div className="text-center p-4 bg-white/40 rounded-2xl border border-white/50 shadow-sm">
                    <div className="text-3xl font-bold text-amber-600">
                      {(dashboardData.todayStats.averageAccuracy * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-gray-500 mt-1.5 font-medium">准确率</div>
                  </div>
                </div>
              </div>
            )}

            {/* 整体进度 */}
            {dashboardData && (
              <div className="glass-card mb-4 rounded-[28px] p-5 border border-white/40 shadow-sm">
                <div className="flex items-center mb-4">
                  <TrendingUp className="mr-2 text-indigo-500" size={20} />
                  <h3 className="text-lg font-bold text-gray-800">整体进度</h3>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between items-end mb-2">
                      <span className="text-base text-gray-500 font-medium">已学词汇</span>
                      <span className="text-lg font-bold text-gray-800">
                        {dashboardData.overallProgress.studiedWords} <span className="text-sm text-gray-400 font-normal">/ {dashboardData.overallProgress.totalWords}</span>
                      </span>
                    </div>
                    <Progress 
                      value={(dashboardData.overallProgress.studiedWords / dashboardData.overallProgress.totalWords) * 100} 
                      className="h-2 bg-white/50 [&>div]:bg-gradient-to-r [&>div]:from-blue-400 [&>div]:to-indigo-500"
                    />
                  </div>
                  
                  <div>
                    <div className="flex justify-between items-end mb-2">
                      <span className="text-base text-gray-500 font-medium">平均掌握度</span>
                      <span className="text-lg font-bold text-emerald-600">
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
                onClick={() => router.push('/today-review')}
                className="glass-card flex flex-col items-center justify-center p-5 rounded-[24px] text-gray-700 hover:text-indigo-600 hover:bg-white/50 border border-white/40 shadow-sm relative overflow-hidden transition-all duration-300"
              >
                <div className="bg-indigo-50 text-indigo-500 p-3 rounded-2xl mb-3">
                  <Clock size={24} />
                </div>
                <span className="text-base font-bold">今日复习</span>
                {dashboardData && dashboardData.dueReviews > 0 && (
                  <span className="absolute top-2.5 right-2.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-500 text-xs font-bold text-white shadow-sm ring-2 ring-white/50">
                    {dashboardData.dueReviews > 99 ? '99+' : dashboardData.dueReviews}
                  </span>
                )}
              </button>
              <button
                onClick={() => router.push('/word-learning-entrance')}
                className="glass-card flex flex-col items-center justify-center p-5 rounded-[24px] text-gray-700 hover:text-indigo-600 hover:bg-white/50 border border-white/40 shadow-sm transition-all duration-300"
              >
                <div className="bg-purple-50 text-purple-500 p-3 rounded-2xl mb-3">
                  <BookOpen size={24} />
                </div>
                <span className="text-base font-bold">开始学习</span>
              </button>
            </div>
          </div>

          {/* Bottom Actions */}
          <div className="px-5 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] shrink-0 pt-3">
            <Button
              variant="ghost"
              onClick={() => router.push('/')}
              className="w-full h-11 rounded-[14px] text-gray-500 hover:text-indigo-600 hover:bg-white/40 text-sm font-medium transition-colors"
            >
              返回主页
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
