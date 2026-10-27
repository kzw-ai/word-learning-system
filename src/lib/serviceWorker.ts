/**
 * Service Worker 注册和管理工具
 */

export interface ServiceWorkerConfig {
  onSuccess?: (registration: ServiceWorkerRegistration) => void;
  onUpdate?: (registration: ServiceWorkerRegistration) => void;
  onError?: (error: Error) => void;
}

/**
 * 注册 Service Worker
 */
export function registerServiceWorker(config?: ServiceWorkerConfig) {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    console.warn('Service Worker 不支持当前浏览器');
    return;
  }

  const register = () => {
    const swUrl = '/service-worker.js';

    navigator.serviceWorker
      .register(swUrl)
      .then((registration) => {
        console.log('✅ Service Worker 注册成功:', registration);

        // 检查更新
        registration.onupdatefound = () => {
          const installingWorker = registration.installing;
          if (installingWorker == null) {
            return;
          }

          installingWorker.onstatechange = () => {
            if (installingWorker.state === 'installed') {
              if (navigator.serviceWorker.controller) {
                // 新的 Service Worker 安装时自行 skipWaiting 接管，接管后由下面的
                // controllerchange 刷新页面，无需再弹窗询问
                console.log('🔄 检测到新版本，准备更新...');
                config?.onUpdate?.(registration);
              } else {
                // 首次安装成功
                console.log('✅ Service Worker 首次安装完成');
                config?.onSuccess?.(registration);
              }
            }
          };
        };
      })
      .catch((error) => {
        console.error('❌ Service Worker 注册失败:', error);
        config?.onError?.(error);
      });

    // 监听 Service Worker 控制器变化
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (refreshing) return;
      refreshing = true;
      console.log('🔄 Service Worker 控制器已更新，刷新页面...');
      window.location.reload();
    });
  };

  // 本函数在 React 的 useEffect 里调用，此时 load 事件通常已经触发过，
  // 只监听 load 会导致 Service Worker 有时根本注册不上
  if (document.readyState === 'complete') {
    register();
  } else {
    window.addEventListener('load', register, { once: true });
  }
}

/**
 * 注销 Service Worker
 */
export async function unregisterServiceWorker() {
  if ('serviceWorker' in navigator) {
    const registration = await navigator.serviceWorker.ready;
    await registration.unregister();
    console.log('🗑️ Service Worker 已注销');
  }
}

/**
 * 清除所有缓存
 */
export async function clearAllCaches() {
  if ('caches' in window) {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames.map((cacheName) => caches.delete(cacheName))
    );
    console.log('🗑️ 所有缓存已清除');
  }
}

/**
 * 检查网络状态
 */
export function checkOnlineStatus(): boolean {
  return navigator.onLine;
}

/**
 * 监听网络状态变化
 */
export function onNetworkStatusChange(
  onOnline: () => void,
  onOffline: () => void
) {
  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);

  // 返回清理函数
  return () => {
    window.removeEventListener('online', onOnline);
    window.removeEventListener('offline', onOffline);
  };
}

/**
 * 预缓存指定URLs
 */
export async function precacheUrls(urls: string[]) {
  if (!('caches' in window)) {
    console.warn('Cache API 不支持');
    return;
  }

  const cache = await caches.open('precache-v1');
  await cache.addAll(urls);
  console.log('✅ 预缓存完成:', urls);
}

/**
 * 获取缓存大小（估算）
 */
export async function getCacheSize(): Promise<number> {
  if (!('caches' in window)) {
    return 0;
  }

  const cacheNames = await caches.keys();
  let totalSize = 0;

  for (const cacheName of cacheNames) {
    const cache = await caches.open(cacheName);
    const requests = await cache.keys();
    
    for (const request of requests) {
      const response = await cache.match(request);
      if (response) {
        const blob = await response.blob();
        totalSize += blob.size;
      }
    }
  }

  return totalSize;
}

/**
 * 格式化缓存大小
 */
export function formatCacheSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

