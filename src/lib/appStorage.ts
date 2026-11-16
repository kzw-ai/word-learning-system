import { Capacitor } from '@capacitor/core';
import { Preferences } from '@capacitor/preferences';

// 关键身份键：iOS 在存储紧张时可能清掉 WebView 的 localStorage，这里再备份一份到
// Capacitor Preferences（底层是 NSUserDefaults / SharedPreferences，更持久）。
// 只备份这几个关键键，不整份镜像 localStorage。
const AUTH_KEYS = ['session_token', 'user_id', 'username', 'learningSystem.guestId'] as const;

export const isNativePlatform = () => Capacitor.isNativePlatform();

/**
 * 把某个身份键的值镜像到 Preferences（写 localStorage 的调用方在写完后顺带调它）。
 * 传 null 表示清除。备份失败不影响主流程（localStorage 仍有效）。
 */
export async function persistAuthKey(key: string, value: string | null): Promise<void> {
  if (!isNativePlatform()) return;
  try {
    if (value === null) {
      await Preferences.remove({ key });
    } else {
      await Preferences.set({ key, value });
    }
  } catch {
    // 备份失败：忽略，localStorage 是主存储
  }
}

/**
 * App 启动时把 Preferences 里的关键身份键回填到 localStorage（只在 localStorage 缺失时回填，
 * 避免用旧值覆盖本次已写入的新值）。必须在读身份（LearningContext 初始化）之前 await 完成。
 */
export async function restoreAuthFromPreferences(): Promise<void> {
  if (!isNativePlatform()) return;
  try {
    for (const key of AUTH_KEYS) {
      let local: string | null = null;
      try {
        local = window.localStorage.getItem(key);
      } catch {
        local = null;
      }
      if (local !== null) continue;
      const { value } = await Preferences.get({ key });
      if (value) {
        try {
          window.localStorage.setItem(key, value);
        } catch {
          // 写不进 localStorage 就只在本次生命周期内用内存值
        }
      }
    }
  } catch {
    // 恢复失败：按无备份继续，访客 ID 会重新生成
  }
}
