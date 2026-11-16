const path = require('path');

// App 构建（静态导出）时设为 'export'：网页版仍走默认 server 构建（next start 依赖它）。
// 静态导出不支持 redirects/rewrites，因此导出构建时这两项返回空数组。
const isAppExport = process.env.NEXT_OUTPUT === 'export';

module.exports = {
  eslint: {
    // TODO: 修完存量 lint 错误后移除（npx next lint 查看）
    ignoreDuringBuilds: true,
  },
  // 仅在 App 构建时启用静态导出；trailingSlash 让 /xxx 也生成目录，避免 App 内刷新深链页回首页
  ...(isAppExport
    ? { output: 'export', trailingSlash: true, images: { unoptimized: true } }
    : {}),
  webpack: (config) => {
    config.resolve.alias['@'] = path.resolve(__dirname, 'src');
    return config;
  },
  // 旧路由重定向：/phase2-demo 在 refactor 中更名（静态导出不支持，App 构建时跳过）
  async redirects() {
    if (isAppExport) return [];
    return [
      { source: '/phase2-demo', destination: '/phase-demo', permanent: true },
    ];
  },
  // 浏览器端 API 走相对路径：生产由 Nginx 代理到后端，
  // 本地 dev / npm start 由这里的 rewrites 代理到 Flask (5004)。
  // App 里所有 API 都走 buildApiUrl（绝对地址），不需要 rewrites。
  async rewrites() {
    if (isAppExport) return [];
    const target = (process.env.API_PROXY_TARGET || 'http://localhost:5004').replace(/\/$/, '');
    return [
      { source: '/api/:path*', destination: `${target}/api/:path*` },
      { source: '/word/:id', destination: `${target}/word/:id` },
      { source: '/words', destination: `${target}/words` },
      { source: '/exercise/:path*', destination: `${target}/exercise/:path*` },
    ];
  },
};
