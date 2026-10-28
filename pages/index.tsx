import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from "@/components/ui/button";
import { BookOpen, GraduationCap, ArrowRight, Activity, BarChart2 } from 'lucide-react';
import { fetchJson } from '@/src/lib/apiClient';
import { useLearningContext } from '@/src/context/LearningContext';
import { reviewedToday, useLearningSession } from '@/src/context/LearningSessionContext';
import { Onboarding, onboardingSeen } from '@/components/Onboarding';

const Home = () => {
  const router = useRouter();
  const { userId } = useLearningContext();
  const { session, hydrated, serverStateLoaded, updateSession } = useLearningSession();
  // null = 加载中，加载失败按 0 处理（不阻塞主流程）
  const [dueIds, setDueIds] = useState<number[] | null>(null);
  // 到期列表是为哪个身份成功取回的（失败也会把 dueIds 置为空，不能据此判断是新用户；
  // 记身份而不是布尔，切换身份后不会沿用上一个身份的结果）
  const [dueLoadedFor, setDueLoadedFor] = useState<string | null>(null);
  const dueLoaded = Boolean(userId) && dueLoadedFor === userId;
  // 今天已复习过的词不算到期，与复习列表的过滤口径一致
  const reviewed = reviewedToday(session);
  const dueCount = dueIds === null ? null : dueIds.filter(id => !reviewed.includes(id)).length;

  // 新用户引导：既没看过引导、也还没有学习记录时自动弹出一次。要等服务器上的学习状态
  // 和到期列表都成功取回：老用户换设备登录时本地是空的，学习位置要从服务器取回才知道
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [autoOpened, setAutoOpened] = useState(false);
  const isNewLearner = serverStateLoaded && dueLoaded && !session.wordId && (dueIds?.length ?? 0) === 0;
  useEffect(() => {
    if (isNewLearner && !onboardingSeen()) {
      setShowOnboarding(true);
      setAutoOpened(true);
    }
  }, [isNewLearner]);
  // 自动弹出后才发现有学习记录（服务器状态稍后才合并进来）：收起，不记为看过
  useEffect(() => {
    if (autoOpened && session.wordId) {
      setShowOnboarding(false);
      setAutoOpened(false);
    }
  }, [autoOpened, session.wordId]);

  // 回到首页即结束复习：中途离开复习（浏览器返回、看板「返回主页」等）后，
  // 之后再开始的普通学习不能还带着复习模式
  useEffect(() => {
    if (hydrated && session.reviewMode) {
      updateSession({ reviewMode: null });
    }
  }, [hydrated, session.reviewMode, updateSession]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    fetchJson<{ success: boolean; data: { word_id: number }[] }>(`/api/review/user/${userId}/due?limit=200`)
      .then(result => {
        if (cancelled) return;
        const ok = result.success && Array.isArray(result.data);
        setDueIds(ok ? result.data.map(r => r.word_id) : []);
        setDueLoadedFor(ok ? userId : null);
      })
      .catch(() => {
        if (cancelled) return;
        setDueIds([]);
        setDueLoadedFor(null);
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  // 主入口的智能路由：有到期复习先复习（记忆曲线优先），否则直接学新词
  const hasDue = (dueCount ?? 0) > 0;
  const handleStartLearning = () => {
    router.push(hasDue ? '/today-review' : '/word-learning-entrance');
  };

  const mainSubtitle =
    dueCount === null
      ? 'Planning today’s session…'
      : hasDue
        ? `${dueCount} ${dueCount === 1 ? 'word' : 'words'} due · review first, then a new word`
        : 'Nothing due today · start a new word';

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-[calc(env(safe-area-inset-bottom)+1rem)] px-5 flex flex-col justify-center relative z-10">
          {/* Header section with glass effect */}
          <div className="text-center mb-6 glass-panel py-6 px-5 rounded-3xl mx-1 shadow-lg border border-white/50 backdrop-blur-xl">
            <div className="w-14 h-14 bg-gradient-to-tr from-indigo-500 to-purple-500 rounded-2xl mx-auto mb-3 flex items-center justify-center shadow-lg shadow-indigo-200">
              <BookOpen className="text-white" size={28} />
            </div>
            <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-gray-900 to-gray-600 leading-tight mb-2 tracking-tight">
              Word Learning
            </h1>
            <p className="text-sm font-medium text-gray-500 tracking-wide uppercase">
              Adaptive Chinese vocabulary
            </p>
          </div>

          <div className="space-y-4">
            {/* 智能主入口：系统决定“下一步做什么”，用户只需要点它 */}
            <button
              onClick={handleStartLearning}
              className="w-full relative overflow-hidden rounded-2xl p-5 shadow-lg shadow-indigo-200 hover:shadow-xl hover:shadow-indigo-300 transition-all duration-300 flex items-center justify-between bg-gradient-to-r from-indigo-500 to-purple-600"
            >
              <div className="flex items-center relative z-10 gap-4">
                <div className="bg-white/20 p-3 rounded-xl text-white backdrop-blur-sm">
                  <GraduationCap size={24} />
                </div>
                <div className="text-left">
                  <p className="font-bold text-white text-lg">Start learning</p>
                  <p className="text-sm text-indigo-100">{mainSubtitle}</p>
                </div>
              </div>
              <div className="bg-white/20 p-2 rounded-full text-white relative z-10">
                <ArrowRight size={20} />
              </div>
            </button>

            {/* 学习路线说明：回答“到底怎么学”，点开是完整的新用户引导 */}
            <button
              type="button"
              onClick={() => setShowOnboarding(true)}
              className="glass-card rounded-2xl px-4 py-3 text-left w-full"
            >
              <p className="text-xs font-semibold text-gray-500 mb-1.5 tracking-wide">
                How it works <span className="text-indigo-700">· see the guide</span>
              </p>
              <p className="text-sm text-gray-600 leading-relaxed">
                Review due words → rate a new word → start at your level:
                <span className="text-indigo-600 font-medium"> characters / word / collocations / sentences </span>
                → practice. Your next review is scheduled for you.
              </p>
            </button>

            {/* 数据入口：易混词辨析已融入主学习流程（练习后自动带出），
                今日复习由主入口按记忆曲线安排，均不再单独设入口 */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 tracking-wide px-1">Your data</p>
              <div className={`grid gap-2 ${process.env.NODE_ENV !== 'production' ? 'grid-cols-2' : 'grid-cols-1'}`}>
                <button
                  onClick={() => router.push('/learning-dashboard')}
                  className="glass-card rounded-2xl px-4 py-3 flex items-center gap-3"
                >
                  <div className="bg-blue-50 text-blue-500 p-2 rounded-lg shrink-0">
                    <Activity size={18} />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-semibold text-gray-700">My progress</p>
                    <p className="text-xs text-gray-500">Progress & suggestions</p>
                  </div>
                </button>

                {/* 全站统计（会话总数、引擎开关），面向开发者，不展示给学习者 */}
                {process.env.NODE_ENV !== 'production' && (
                  <button
                    onClick={() => router.push('/learning-stats')}
                    className="glass-card rounded-2xl px-4 py-3 flex items-center gap-3"
                  >
                    <div className="bg-emerald-50 text-emerald-500 p-2 rounded-lg shrink-0">
                      <BarChart2 size={18} />
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-semibold text-gray-700">System stats</p>
                      <p className="text-xs text-gray-500">For developers</p>
                    </div>
                  </button>
                )}
              </div>
            </div>

            {/* Bottom minor actions */}
            <div className="flex gap-3 pt-1">
              <Button
                variant="ghost"
                onClick={() => router.push('/login')}
                className="flex-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-white/50 h-10 rounded-xl"
              >
                Sign in
              </Button>
              {/* 端口探测页，面向开发者，不展示给学习者 */}
              {process.env.NODE_ENV !== 'production' && (
                <Button
                  variant="ghost"
                  onClick={() => router.push('/system-status')}
                  className="flex-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-white/50 h-10 rounded-xl"
                >
                  Diagnostics
                </Button>
              )}
            </div>
          </div>
        </div>

        <Onboarding
          open={showOnboarding}
          onClose={() => {
            setShowOnboarding(false);
            setAutoOpened(false);
          }}
        />

        {/* Decorative floating blur circles */}
        <div className="absolute -top-20 -right-20 w-48 h-48 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 pointer-events-none"></div>
        <div className="absolute top-40 -left-20 w-48 h-48 bg-indigo-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 pointer-events-none"></div>
      </div>
    </div>
  );
};

export default Home;
