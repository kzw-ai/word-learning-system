import React from 'react';
import { useRouter } from 'next/router';
import { Button } from '@/components/ui/button';

/**
 * 隐私政策页面。
 * 两个应用商店提交时都要填隐私政策网址，网页版也会随静态导出生成 /privacy。
 * 正文占位，正式文案由作者提供后再替换。
 */
const PrivacyPolicy = () => {
  const router = useRouter();
  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-[calc(env(safe-area-inset-bottom)+1rem)] px-5 flex flex-col relative z-20">
          <div className="flex items-center justify-between mb-4 shrink-0">
            <Button
              variant="ghost"
              onClick={() => router.push('/')}
              className="h-9 px-3 rounded-xl bg-white/80 hover:bg-white border border-slate-200/70 shadow-sm text-indigo-700 text-sm font-semibold"
            >
              ← Home
            </Button>
            <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">Privacy Policy</h1>
            <span className="w-16" aria-hidden="true" />
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar scroll-fade pb-4">
            <div className="glass-panel rounded-3xl p-5 space-y-3">
              <h2 className="text-lg font-bold text-slate-900">Privacy Policy</h2>
              {/* TODO: 正文由作者提供，替换下面的占位说明 */}
              <p className="text-sm text-slate-600 leading-relaxed">
                This is placeholder content. The full privacy policy text will be provided by the author.
              </p>
              <p className="text-sm text-slate-600 leading-relaxed">
                Word Learning keeps your learning progress with a guest identity or a signed-in
                account. Learning records are stored on the server and are associated only with your
                account or this device&apos;s guest ID, so you can pick up where you left off.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
