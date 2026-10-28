// Service Worker for offline caching
//
// v1 对所有同源 GET 一律「缓存优先」，连页面和 /api/ 接口都只取第一次缓存的结果：
// 老用户永远看不到新部署的页面，到期复习、练习题等接口数据也冻结在第一次请求时。
// v2 改为：接口不缓存；页面网络优先、断网才用缓存；只有带内容哈希的
// /_next/static/ 静态资源缓存优先。改名为 v2 后，activate 会删掉 v1 的旧缓存。
// v3：界面改为英文，换掉缓存里的中文离线页与清单。
const CACHE_NAME = 'word-learning-v3';
const urlsToCache = [
  '/manifest.json',
  '/offline.html'
];

// 安装 Service Worker
self.addEventListener('install', (event) => {
  console.log('[Service Worker] 安装中...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[Service Worker] 缓存文件');
        return cache.addAll(urlsToCache);
      })
      .catch((error) => {
        console.error('[Service Worker] 缓存失败:', error);
      })
  );
  // 强制新的 Service Worker 立即激活
  self.skipWaiting();
});

// 激活 Service Worker
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] 激活中...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[Service Worker] 删除旧缓存:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // 立即控制所有页面
  return self.clients.claim();
});

// 拦截请求
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 非 GET、非 http(s)、跨域请求不处理
  if (request.method !== 'GET' || !url.protocol.startsWith('http') || url.origin !== location.origin) {
    return;
  }

  // 后端数据接口（由 Next 转发到 Flask）永远走网络，绝不缓存
  if (url.pathname.startsWith('/api/') || url.pathname === '/words' || url.pathname.startsWith('/word/')) {
    return;
  }

  // 文件名带内容哈希，内容变了文件名就变，可以安全地缓存优先
  if (url.pathname.startsWith('/_next/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetchAndCache(request))
    );
    return;
  }

  // 页面与其他资源：网络优先，失败时才用缓存，页面再退到离线页
  event.respondWith(
    fetchAndCache(request).catch(() =>
      caches.match(request).then((cached) => {
        if (cached) return cached;
        if (request.mode === 'navigate') return caches.match('/offline.html');
        return new Response('Network error', {
          status: 408,
          statusText: 'Network Error',
          headers: { 'Content-Type': 'text/plain' }
        });
      })
    )
  );
});

function fetchAndCache(request) {
  return fetch(request).then((response) => {
    if (response && response.status === 200 && response.type === 'basic') {
      const copy = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
    }
    return response;
  });
}

// 监听消息（可用于手动触发缓存更新）
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => caches.delete(cacheName))
      );
    }).then(() => {
      event.ports[0].postMessage({ success: true });
    });
  }
});

// 同步后台数据（可选）
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-learning-data') {
    event.waitUntil(
      fetch('/api/sync')
        .then((response) => response.json())
        .then((data) => {
          console.log('[Service Worker] 数据同步成功:', data);
        })
        .catch((error) => {
          console.error('[Service Worker] 数据同步失败:', error);
        })
    );
  }
});

