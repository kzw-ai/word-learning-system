import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { buildApiUrl } from "@/src/lib/apiClient";
import { useLearningContext } from '@/src/context/LearningContext';
import { reviewedToday, useLearningSession } from '@/src/context/LearningSessionContext';
import { Clock, BookOpen, CheckCircle2 } from 'lucide-react';

interface ReviewItem {
  word_id: number;
  word: string;
  pinyin?: string;
  mastery_level: number;
  days_overdue: number;
  review_count: number;
  priority_score: number;
  recommended_module: string;
  /** 论文表 4.2 的复习计划：还要复习几次（各题型中最多的那个），0 表示已达标、进入长期巩固 */
  reviews_remaining?: number;
  /** 还需复习的题型 */
  review_types?: string[];
}

const REVIEW_TYPE_LABELS: Record<string, string> = {
  definition: 'meaning',
  collocation: 'collocations',
  // 不断行连字符：窄屏时不在 fill- / in 之间折行
  fill_word: 'fill\u2011in'
};

const TodayReview = () => {
  const router = useRouter();
  const { userId } = useLearningContext();
  const { session, hydrated, updateSession } = useLearningSession();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dueReviews, setReviews] = useState<ReviewItem[]>([]);
  // 列表是哪个用户的：切换用户后，旧用户的（空）列表不能触发对新用户的清理
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const currentUserRef = useRef(userId);
  currentUserRef.current = userId;
  // 点了开始复习、正在跳走：不能在跳走前据列表判定「复习做完了」而清掉复习模式
  const leavingRef = useRef(false);
  // 隐藏今天已经复习完的词（练习页做完时记下，只在当天有效；中途退出的词不隐藏）
  const reviewed = reviewedToday(session);
  const reviews = dueReviews.filter((r) => !reviewed.includes(r.word_id));

  useEffect(() => {
    fetchDueReviews();
  }, [userId]);

  const fetchDueReviews = async () => {
    const requestUser = userId;
    if (!requestUser) return;
    try {
      setLoading(true);
      setLoadedFor(null);
      setReviews([]);
      // limit 取足：前端还要再滤掉今天复习过的词，后端只给前 N 个的话，
      // 排在后面的到期词会被这批挡住、永远轮不到（词库目前约 70 个词）
      const response = await fetch(buildApiUrl(`/api/review/user/${requestUser}/due?limit=200`));
      const result = await response.json();
      if (currentUserRef.current !== requestUser) return;

      if (response.ok && result.success) {
        setReviews(result.data);
        setLoadedFor(requestUser);
      } else {
        setError(result.error || 'The service is unavailable');
      }
    } catch (err) {
      setError('Couldn’t connect. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  // 复习清空后退出复习模式，之后学完的词照常去学习看板。
  // 只退出模式、保留今天的已复习记录：未登录时作答没被记下，后端仍会返回这些词，
  // 清掉记录它们会立刻重新出现
  useEffect(() => {
    if (hydrated && loadedFor === userId && reviews.length === 0 && session.reviewMode && !leavingRef.current) {
      updateSession({ reviewMode: null });
    }
  }, [hydrated, loadedFor, userId, reviews.length, session.reviewMode, updateSession]);

  const startReview = (review: ReviewItem) => {
    leavingRef.current = true;
    // reviewMode：学完这个词后回到本页，接着复习列表里剩下的词。
    // 复习过的词 SM-2 会推后下次复习时间，重新拉取时自然不在列表里了。
    updateSession({
      wordId: review.word_id,
      word: review.word,
      module: review.recommended_module,
      entryModule: review.recommended_module,
      vksLevel: undefined,
      recommendationId: null,
      reviewMode: true,
      // 用户主动开始：即使内容与原来相同也要刷新时间戳
      lastUpdated: new Date().toISOString()
    });

    const moduleRoutes: Record<string, string> = {
      character: '/character-learning',
      word: '/word-learning',
      collocation: '/collocation-learning',
      sentence: '/sentence-learning',
      exercise: '/exercise'
    };

    const route = moduleRoutes[review.recommended_module] || moduleRoutes.word;
    router.push(route);
  };

  const getPriorityBadge = (score: number) => {
    // 浅底深字：白字放在橙底上对比度只有 2 左右
    if (score > 0.8) return <Badge className="bg-rose-50 hover:bg-rose-50 text-rose-800 border border-rose-200 shadow-none text-sm px-2.5 py-0.5 shrink-0">High priority</Badge>;
    if (score > 0.5) return <Badge className="bg-amber-50 hover:bg-amber-50 text-amber-800 border border-amber-200 shadow-none text-sm px-2.5 py-0.5 shrink-0">Medium priority</Badge>;
    return <Badge className="bg-slate-100 hover:bg-slate-100 text-slate-700 border border-slate-200 shadow-none text-sm px-2.5 py-0.5 shrink-0">Low priority</Badge>;
  };

  const getMasteryColor = (level: number) => {
    // 都取同色系深一档，白底上对比度够 4.5
    if (level >= 0.8) return 'text-emerald-700';
    if (level >= 0.6) return 'text-blue-700';
    if (level >= 0.4) return 'text-amber-700';
    return 'text-rose-700';
  };

  const getModuleLabel = (module: string) => {
    const labels: Record<string, string> = {
      character: 'Characters',
      word: 'Word',
      collocation: 'Collocations',
      sentence: 'Sentences',
      exercise: 'Practice'
    };
    return labels[module] || labels.word;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
        <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mb-4"></div>
          <p className="text-base text-gray-600">Loading reviews...</p>
        </div>
      </div>
    );
  }

  // 主动离开即结束本轮复习，下次进来重新开始
  const leaveReview = () => {
    updateSession({ reviewMode: null });
    router.push('/');
  };

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+0.75rem)] flex flex-col relative z-20">
          {/* 顶栏和其他页一样：左回首页（离开即结束本轮复习），中间标题，右边到期个数 */}
          <div className="px-5 pb-2 flex items-center justify-between">
            <Button variant="ghost" onClick={leaveReview} className="h-9 px-3 rounded-xl bg-white/80 hover:bg-white border border-slate-200/70 shadow-sm text-indigo-700 text-sm font-semibold">
              ← Home
            </Button>
            <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">Review</h1>
            <span className="h-9 px-3 inline-flex items-center rounded-xl bg-indigo-50 border border-indigo-100 text-sm font-semibold text-indigo-700 tabular-nums">
              {reviews.length} due
            </span>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3 custom-scrollbar scroll-fade">
            {error && (
              <div className="glass-card p-5 rounded-2xl border border-red-200 bg-red-50/50 text-center">
                <p className="text-base text-rose-700 mb-4">{error}</p>
                <Button 
                  size="sm" 
                  onClick={fetchDueReviews}
                  className="w-full bg-red-500 hover:bg-red-600 text-white rounded-xl h-11 text-base"
                >
                  Reload
                </Button>
              </div>
            )}

            {!error && reviews.length === 0 && (
              <div className="glass-panel p-8 short:p-6 rounded-3xl text-center mt-2">
                <div className="w-14 h-14 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle2 size={30} className="text-emerald-700" aria-hidden="true" />
                </div>
                <p className="text-2xl font-bold text-slate-900 mb-2">All reviews done</p>
                <p className="text-base text-slate-600 mb-6 leading-relaxed">You've completed all your reviews for today.</p>
                <Button 
                  onClick={() => router.push('/word-learning-entrance')}
                  className="w-full h-12 rounded-2xl border-none bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 active:scale-[0.99] text-white text-base font-bold shadow-md shadow-indigo-500/20"
                >
                  Learn a new word
                </Button>
              </div>
            )}

            {reviews.map((review, index) => (
              <div 
                key={`${review.word_id}-${index}`}
                className="glass-card p-4 rounded-2xl hover:border-indigo-200 cursor-pointer"
                onClick={() => startReview(review)}
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1">
                    <h3 className="font-bold text-xl text-slate-900">
                      {review.word}
                      {review.pinyin && review.pinyin !== review.word && (
                        <span className="ml-2 text-sm font-normal text-slate-600">{review.pinyin}</span>
                      )}
                    </h3>
                    <p className="text-sm text-slate-600 mt-1">
                      Reviewed {review.review_count ?? 0} {(review.review_count ?? 0) === 1 ? 'time' : 'times'}
                    </p>
                    {review.reviews_remaining !== undefined && (
                      <p className="text-sm text-indigo-700 mt-0.5">
                        {review.reviews_remaining > 0
                          ? `${review.reviews_remaining} more ${review.reviews_remaining === 1 ? 'review' : 'reviews'} · ${(review.review_types ?? []).map((t) => REVIEW_TYPE_LABELS[t] ?? t).join(', ')}`
                          : 'Mastered · keeping it fresh'}
                      </p>
                    )}
                  </div>
                  {getPriorityBadge(review.priority_score)}
                </div>
                
                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">Mastery</span>
                    <span className={`font-semibold ${getMasteryColor(review.mastery_level)}`}>
                      {(review.mastery_level * 100).toFixed(0)}%
                    </span>
                  </div>
                  
                  <div className="w-full bg-indigo-100/50 rounded-full h-2 overflow-hidden">
                    <div 
                      className={`h-2 rounded-full ${
                        review.mastery_level >= 0.8 ? 'bg-emerald-400' :
                        review.mastery_level >= 0.6 ? 'bg-blue-400' :
                        review.mastery_level >= 0.4 ? 'bg-amber-400' :
                        'bg-rose-400'
                      }`}
                      style={{ width: `${review.mastery_level * 100}%` }}
                    ></div>
                  </div>
                  
                  {review.days_overdue > 0 && (
                    <p className="text-sm text-rose-700 font-medium mt-1 flex items-center gap-1.5">
                      <Clock size={14} aria-hidden="true" />
                      {review.days_overdue} {review.days_overdue === 1 ? 'day' : 'days'} overdue
                    </p>
                  )}
                </div>
                
                <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                  <span className="text-sm text-slate-600 flex items-center font-medium">
                    <BookOpen size={14} className="mr-1.5" />
                    {getModuleLabel(review.recommended_module)}
                  </span>
                  <Button 
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      startReview(review);
                    }}
                    className="h-9 px-4 rounded-xl bg-indigo-50 hover:bg-indigo-100 border border-indigo-100 text-indigo-700 text-sm font-semibold shadow-none"
                  >
                    Review
                  </Button>
                </div>
              </div>
            ))}
          </div>

          {/* 底栏只留一个主按钮：从第一个到期词开始 */}
          {reviews.length > 0 && (
          <div className="px-5 pb-[calc(env(safe-area-inset-bottom)+1rem)] short:pb-[calc(env(safe-area-inset-bottom)+0.75rem)] shrink-0 pt-3 bg-slate-100/95 border-t border-slate-200/70 shadow-[0_-8px_16px_-12px_rgba(15,23,42,0.25)]">
              <Button
                onClick={() => {
                  if (reviews[0]) {
                    startReview(reviews[0]);
                  }
                }}
                className="w-full h-12 rounded-2xl border-none bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 active:scale-[0.99] text-white text-base font-bold shadow-md shadow-indigo-500/20"
              >
                {session.reviewMode ? `Continue review (${reviews.length} left)` : 'Start first review'}
              </Button>
          </div>
          )}
        </div>

        {/* Decorative blurs */}
        <div className="absolute top-1/3 -right-12 w-48 h-48 bg-indigo-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>
        <div className="absolute bottom-1/3 -left-12 w-48 h-48 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 pointer-events-none z-10"></div>
      </div>
    </div>
  );
};

export default TodayReview;
