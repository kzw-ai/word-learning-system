import React, { useEffect } from 'react';
import '../styles/globals.css';
import '../styles/mobile.css';
import { AppProps } from 'next/app';
import UserSwitcher from '@/components/UserSwitcher';
import NetworkStatus from '@/components/NetworkStatus';
import { LearningProvider } from '@/src/context/LearningContext';
import { LearningSessionProvider } from '@/src/context/LearningSessionContext';
import { registerServiceWorker } from '@/src/lib/serviceWorker';
import { useViewportHeight } from '@/src/hooks/useMobileOptimization';
import { Capacitor } from '@capacitor/core';

function MyApp({ Component, pageProps }: AppProps) {
  // 修复移动端视口高度问题
  useViewportHeight();

  useEffect(() => {
    // App（Capacitor）里不需要 Service Worker：页面由 WebView 本地加载，SW 会与原生壳抢缓存
    if (Capacitor.isNativePlatform()) return;
    registerServiceWorker({
      onSuccess: () => {
        console.log('✅ PWA 已就绪，支持离线访问');
      },
      onUpdate: () => {
        console.log('🔄 检测到新版本');
      },
      onError: (error) => {
        console.error('❌ Service Worker 注册失败:', error);
      }
    });
  }, []);

  return (
    <LearningProvider>
      <LearningSessionProvider>
        <Component {...pageProps} />
        {/* 切换测试用户的调试工具：生产环境不显示，它会悬浮遮住各页的主按钮 */}
        {process.env.NODE_ENV !== 'production' && <UserSwitcher />}
        <NetworkStatus />
      </LearningSessionProvider>
    </LearningProvider>
  );
}

export default MyApp;
