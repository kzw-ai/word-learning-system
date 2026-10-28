import React from 'react';
import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        {/* PWA Manifest */}
        <link rel="manifest" href="/manifest.json" />
        
        {/* PWA 图标 */}
        <link rel="icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" href="/icon-192.png" />
        
        {/* PWA 主题颜色 */}
        <meta name="theme-color" content="#ff6b35" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Word Learning" />
        
        {/* PWA 描述 */}
        <meta name="description" content="Adaptive Chinese vocabulary learning for intermediate learners, guided by the Vocabulary Knowledge Scale" />
        <meta name="keywords" content="Chinese vocabulary,HSK,Mandarin,VKS,adaptive learning,spaced repetition" />
        
        {/* 视口设置 */}
        {/* 允许双指缩放（看清汉字笔画、无障碍）；viewport-fit=cover 才能让 iOS 上的
            env(safe-area-inset-*) 取到真实的刘海/底部安全区 */}
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}

