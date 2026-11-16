import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { LearningProvider } from '@/context/LearningContext';
import { LearningSessionProvider } from '@/context/LearningSessionContext';

export default function RootLayout() {
  return (
    <LearningProvider>
      <LearningSessionProvider>
        <StatusBar style="dark" />
        {/* 学习流程是线性的，用 Stack 导航；各页自带顶栏，隐藏原生 header */}
        <Stack screenOptions={{ headerShown: false }} />
      </LearningSessionProvider>
    </LearningProvider>
  );
}
