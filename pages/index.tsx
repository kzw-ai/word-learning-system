import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from "@/components/ui/button";
import { BookOpen, ArrowRight, BarChart2, Gauge, CalendarClock, Scale, ChevronRight } from 'lucide-react';
import { fetchJson } from '@/src/lib/apiClient';
import { useLearningContext } from '@/src/context/LearningContext';
import { reviewedToday, useLearningSession } from '@/src/context/LearningSessionContext';
import { Onboarding, onboardingSeen } from '@/components/Onboarding';

// 首页分两版：第一次来的人看到「这是什么、好在哪」（示例词卡和三条做法），
// 学过的人直接看到「今天」：到期几个、四级词学了多少，一个按钮开始。
// 不在首页取推荐的下一个词：推荐接口每调一次就记一条推荐，首页打开得多，会堆出大量没有反馈的记录

/** 示例词卡：田字格里的字（练字本的格子，学中文的人一眼认得） */
const GridCell = ({ char, small = false }: { char: string; small?: boolean }) => (
  <span className={`relative inline-flex items-center justify-center rounded-lg bg-white border border-rose-200 font-bold text-slate-900 leading-none ${
    small ? 'w-11 h-11 text-[26px]' : 'w-14 h-14 short:w-12 short:h-12 text-[34px] short:text-[30px]'}`} lang="zh-CN">
    <span className="absolute inset-x-0 top-1/2 border-t border-dashed border-rose-200" aria-hidden="true" />
    <span className="absolute inset-y-0 left-1/2 border-l border-dashed border-rose-200" aria-hidden="true" />
    <span className="relative">{char}</span>
  </span>
);

const POINTS = [
  { icon: Gauge, title: 'Starts at your level', text: 'Rate each new word first and skip what you already know.' },
  { icon: CalendarClock, title: 'Reviews before you forget', text: 'Each word comes back a few days apart, until it sticks.' },
  { icon: Scale, title: 'Tells confusable words apart', text: 'Pairs like 突然 and 忽然, with sentences to choose between.' },
];

interface HomeStats {
  hsk4Words: number;
  hsk4Studied: number;
}

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
  const [stats, setStats] = useState<HomeStats | null>(null);
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
    // 四级词进度（只读统计，取不到就不显示进度卡）
    fetchJson<{ success: boolean; data: { overallProgress: HomeStats } }>(`/api/analytics/user/${userId}/dashboard`)
      .then(result => {
        if (!cancelled && result.success) setStats(result.data.overallProgress);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [userId]);

  // 学过的人：本机或服务器上有学习位置、有到期复习、或学过四级词
  const returning = Boolean(session.wordId) || (dueIds?.length ?? 0) > 0 || (stats?.hsk4Studied ?? 0) > 0;

  // 主入口的智能路由：有到期复习先复习（记忆曲线优先），否则直接学新词
  const hasDue = (dueCount ?? 0) > 0;
  const handleStartLearning = () => {
    router.push(hasDue ? '/today-review' : '/word-learning-entrance');
  };

  const devLinks = process.env.NODE_ENV !== 'production' && (
    // 全站统计和端口探测，面向开发者，不展示给学习者
    <div className="flex gap-2">
      <Button variant="ghost" onClick={() => router.push('/learning-stats')} className="flex-1 h-9 rounded-xl text-sm font-semibold text-slate-600 hover:bg-white/60">
        <BarChart2 size={16} className="mr-1.5" /> System stats
      </Button>
      <Button variant="ghost" onClick={() => router.push('/system-status')} className="flex-1 h-9 rounded-xl text-sm font-semibold text-slate-600 hover:bg-white/60">
        Diagnostics
      </Button>
    </div>
  );

  const howItWorks = (
    <button
      type="button"
      onClick={() => setShowOnboarding(true)}
      className="h-9 px-2 text-sm font-semibold text-indigo-700 hover:text-indigo-900 rounded-lg"
    >
      How it works
    </button>
  );

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        {/* 放得下时上下居中，放不下时整页可以滚（小屏上不能把头尾裁掉） */}
        <div className="h-full overflow-y-auto relative z-10">
        <div className="min-h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-[calc(env(safe-area-inset-bottom)+1rem)] px-5 flex flex-col">
          {/* 顶栏：应用名和级别，右边登录 */}
          <header className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 bg-gradient-to-tr from-indigo-500 to-violet-600 rounded-xl flex items-center justify-center shadow-sm shadow-indigo-200">
                <BookOpen className="text-white" size={18} />
              </div>
              <span className="text-base font-extrabold text-slate-900 tracking-tight">Word Learning</span>
              <span className="text-sm font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-full px-2 leading-6">HSK 4</span>
            </div>
            <Button
              variant="ghost"
              onClick={() => router.push('/login')}
              className="h-9 px-3 rounded-xl text-sm font-semibold text-slate-600 hover:text-slate-800 hover:bg-white/60"
            >
              Sign in
            </Button>
          </header>

          {!hydrated ? null : returning ? (
            // 学过的人：今天要做什么、学到哪了
            // 从上往下排：内容不多，居中会在大屏上方空出一大块
            <main className="flex-1 flex flex-col gap-4 pt-8 short:pt-5 pb-6">
              <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight px-1">Welcome back</h1>

              <section className="glass-panel rounded-3xl p-5 short:p-4" aria-label="Today">
                <div className="flex items-start justify-between gap-3">
                <div>
                <p className="text-sm font-semibold text-indigo-700">Today</p>
                <p className="mt-1 text-xl font-bold text-slate-900">
                  {dueCount === null
                    ? 'Planning today…'
                    : hasDue
                      ? `${dueCount} ${dueCount === 1 ? 'word' : 'words'} to review`
                      : 'All reviews done'}
                </p>
                <p className="text-sm text-slate-600">
                  {hasDue ? 'Reviews first, then a new word.' : 'Time for a new word.'}
                </p>
                </div>
                {/* 上次学的词：两个字以内放在田字格里，更长的词格子太宽、挤窄左边的文字，直接显示 */}
                {session.word && (
                  <div className="shrink-0 text-center" aria-label={`Last word: ${session.word}`}>
                    {Array.from(session.word).length <= 2 ? (
                      <span className="flex gap-1">
                        {Array.from(session.word).map((ch, i) => <GridCell key={i} char={ch} small />)}
                      </span>
                    ) : (
                      <span className="block text-2xl font-bold text-slate-900 leading-[44px]" lang="zh-CN">{session.word}</span>
                    )}
                    <span className="block mt-1 text-sm text-slate-500">Last word</span>
                  </div>
                )}
                </div>
                <button
                  onClick={handleStartLearning}
                  className="mt-4 w-full h-12 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-base font-bold shadow-md shadow-indigo-500/20 active:scale-[0.99] transition-transform flex items-center justify-center gap-2"
                >
                  {hasDue ? `Review ${dueCount} ${dueCount === 1 ? 'word' : 'words'}` : 'Learn a new word'}
                  <ArrowRight size={18} />
                </button>
              </section>

              {stats && stats.hsk4Words > 0 && (
                <button
                  onClick={() => router.push('/learning-dashboard')}
                  className="glass-card rounded-2xl px-4 py-3.5 text-left"
                  aria-label={`HSK 4 words: ${stats.hsk4Studied} of ${stats.hsk4Words} studied. Open my progress`}
                >
                  <span className="flex items-baseline justify-between">
                    <span className="text-sm font-semibold text-slate-700">HSK 4 words</span>
                    <span className="text-sm font-bold text-slate-900 tabular-nums">
                      {stats.hsk4Studied}<span className="font-medium text-slate-500"> / {stats.hsk4Words}</span>
                    </span>
                  </span>
                  <span className="mt-2 block h-2 rounded-full bg-slate-200 overflow-hidden">
                    <span
                      className="block h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                      style={{ width: `${stats.hsk4Studied > 0 ? Math.max(2, Math.round((stats.hsk4Studied / stats.hsk4Words) * 100)) : 0}%` }}
                    />
                  </span>
                  <span className="mt-2 flex items-center justify-end text-sm font-semibold text-indigo-700">
                    My progress <ChevronRight size={16} />
                  </span>
                </button>
              )}

              <div className="flex justify-center">{howItWorks}</div>
              {devLinks}
            </main>
          ) : (
            // 第一次来：是什么、怎么学，一个按钮开始
            <main className="flex-1 flex flex-col justify-center gap-5 short:gap-3.5 py-6 short:py-4">
              <div className="px-1">
                <h1 className="text-[28px] short:text-2xl font-extrabold text-slate-900 leading-tight tracking-tight" style={{ textWrap: 'balance' }}>
                  Learn the 600 HSK 4 words
                </h1>
                <p className="mt-1.5 text-base short:text-sm text-slate-600">
                  Characters, the word, its phrases and sentences, then practice.
                </p>
              </div>

              {/* 示例词卡：学习页上的真实内容（师傅） */}
              <section className="glass-panel rounded-3xl p-4 flex items-center gap-4" aria-label="Example word">
                <span className="flex gap-1 shrink-0">
                  <GridCell char="师" />
                  <GridCell char="傅" />
                </span>
                <span className="min-w-0">
                  <span className="block text-lg font-bold text-indigo-700 leading-tight">shīfu</span>
                  <span className="block text-sm text-slate-600">master; qualified worker</span>
                  <span className="block mt-1 text-sm text-slate-800 truncate" lang="zh-CN">我师傅教我怎么用这个机器。</span>
                </span>
              </section>

              <ul className="space-y-3 short:space-y-2">
                {POINTS.map(({ icon: Icon, title, text }) => (
                  // 矮屏上不显示说明，只剩标题一行：图标和标题垂直居中
                  <li key={title} className="flex items-start short:items-center gap-3 px-1">
                    <span className="w-9 h-9 shrink-0 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600 flex items-center justify-center">
                      <Icon size={18} />
                    </span>
                    <span>
                      <span className="block text-base short:text-sm font-semibold text-slate-900 leading-snug">{title}</span>
                      <span className="block text-sm text-slate-600 leading-snug short:hidden">{text}</span>
                    </span>
                  </li>
                ))}
              </ul>

              <div className="space-y-1">
                <button
                  onClick={handleStartLearning}
                  className="w-full h-12 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-base font-bold shadow-md shadow-indigo-500/20 active:scale-[0.99] transition-transform flex items-center justify-center gap-2"
                >
                  Start my first word <ArrowRight size={18} />
                </button>
                <div className="flex justify-center">{howItWorks}</div>
              </div>
              {devLinks}
            </main>
          )}
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
