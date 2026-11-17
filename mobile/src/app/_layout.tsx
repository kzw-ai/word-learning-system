import { Stack } from 'expo-router';
import { useEffect } from 'react';
import { setAudioModeAsync } from 'expo-audio';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { StatusBar } from 'expo-status-bar';
import { LearningProvider } from '@/context/LearningContext';
import { LearningSessionProvider } from '@/context/LearningSessionContext';

export default function RootLayout() {
  // 音频会话（全局设置一次）：iOS 静音键打开时也要出声；用户在听音乐时，发音只把音乐压低，不打断（方案第 3 节 duckOthers）
  useEffect(() => {
    setAudioModeAsync({ playsInSilentMode: true, interruptionMode: 'duckOthers' }).catch(() => {});
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <LearningProvider>
        <LearningSessionProvider>
          <StatusBar style="dark" />
          {/* 学习流程是线性的，用 Stack 导航；各页自带顶栏，隐藏原生 header。
              学习页禁用 iOS 边缘右滑返回手势：手写横笔会被系统误判成返回手势，把练习页滑走 */}
          <Stack screenOptions={{ headerShown: false, gestureEnabled: false }} />
        </LearningSessionProvider>
      </LearningProvider>
    </GestureHandlerRootView>
  );
}
