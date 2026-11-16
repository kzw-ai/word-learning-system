import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      {/* 学习流程是线性的，用 Stack 导航；各页自带顶栏，隐藏原生 header */}
      <Stack screenOptions={{ headerShown: false }} />
    </>
  );
}
