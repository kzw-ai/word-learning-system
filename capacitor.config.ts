import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'top.kzwbelieve.learnchinese',
  appName: 'Word Learning',
  webDir: 'out',
  server: {
    // 安卓 WebView 的来源是 https://localhost（https 才能满足安全来源要求）
    androidScheme: 'https',
  },
};

export default config;
