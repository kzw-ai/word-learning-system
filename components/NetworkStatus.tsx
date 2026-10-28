import React, { useEffect, useState } from 'react';
import { Wifi, WifiOff } from 'lucide-react';
import { checkOnlineStatus, onNetworkStatusChange } from '@/src/lib/serviceWorker';

/**
 * 网络状态指示器组件
 * 显示当前网络连接状态，离线时显示提示
 */
export default function NetworkStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const [showToast, setShowToast] = useState(false);

  useEffect(() => {
    // 初始检查
    setIsOnline(checkOnlineStatus());

    // 监听网络状态变化
    const cleanup = onNetworkStatusChange(
      () => {
        setIsOnline(true);
        setShowToast(true);
        setTimeout(() => setShowToast(false), 3000);
      },
      () => {
        setIsOnline(false);
        setShowToast(true);
      }
    );

    return cleanup;
  }, []);

  if (isOnline && !showToast) {
    return null; // 在线且不显示提示时隐藏
  }

  return (
    <div
      className={`
        fixed top-4 right-4 z-50
        px-4 py-2 rounded-lg shadow-lg
        flex items-center gap-2
        transition-all duration-300
        ${isOnline 
          ? 'bg-green-500 text-white' 
          : 'bg-red-500 text-white'
        }
        ${showToast ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2'}
      `}
    >
      {isOnline ? (
        <>
          <Wifi size={20} />
          <span className="font-medium">Back online</span>
        </>
      ) : (
        <>
          <WifiOff size={20} />
          <span className="font-medium">You're offline</span>
        </>
      )}
    </div>
  );
}

/**
 * 离线横幅组件
 * 持续显示在页面顶部，直到网络恢复
 */
export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    setIsOnline(checkOnlineStatus());

    const cleanup = onNetworkStatusChange(
      () => setIsOnline(true),
      () => setIsOnline(false)
    );

    return cleanup;
  }, []);

  if (isOnline) {
    return null;
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-40 bg-yellow-500 text-white px-4 py-2 text-center text-sm font-medium">
      <WifiOff size={16} className="inline mr-2" />
      You're offline — some features may not work
    </div>
  );
}

