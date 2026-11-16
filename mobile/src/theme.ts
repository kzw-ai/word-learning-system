// 复用网页版的配色与规格（styles/globals.css、tailwind.config.js、各页面）。
// 界面文字为英文、学习内容为中文；正文字号不小于 14，按钮高度不小于 36。
export const colors = {
  bgStart: '#f8fafc', // slate-50
  bgEnd: '#f1f5f9', // slate-100
  primary: '#4f46e5', // indigo-600
  primaryDark: '#4338ca', // indigo-700
  primaryDeep: '#3730a3', // indigo-800
  primaryLight: '#6366f1', // indigo-500
  primaryBg: '#eef2ff', // indigo-50
  primaryBorder: '#e0e7ff', // indigo-100
  accent: '#7c3aed', // violet-600
  accentLight: '#8b5cf6', // violet-500
  text: '#0f172a', // slate-900
  textStrong: '#334155', // slate-700
  textMuted: '#475569', // slate-600
  textFaint: '#64748b', // slate-500
  border: '#e2e8f0', // slate-200
  borderStrong: '#cbd5e1', // slate-300
  white: '#ffffff',
  success: '#047857', // emerald-700
  successBg: '#ecfdf5', // emerald-50
  successBorder: '#a7f3d0', // emerald-200
  danger: '#e11d48', // rose-600
  dangerText: '#be123c', // rose-700
  dangerBg: '#fff1f2', // rose-50
  dangerBorder: '#fecdd3', // rose-200
  warning: '#b45309', // amber-700
  amberText: '#92400e', // amber-800
  amberBg: '#fffbeb', // amber-50
  amberBorder: '#fde68a', // amber-200
};

export const radius = {
  sm: 6,
  md: 8, // lg
  lg: 12, // xl
  xl: 16, // 2xl
  '2xl': 20,
  '3xl': 24,
  full: 9999,
};

export const fontSize = {
  body: 14, // text-sm，正文最小字号
  base: 16, // text-base
  lg: 18, // text-lg
  xl: 20, // text-xl
  '2xl': 24, // text-2xl
  '3xl': 30, // text-3xl
};

export const buttonHeight = {
  min: 36, // h-9，最小触控高度
  md: 40, // h-10
  lg: 44, // h-11
  xl: 48, // h-12，主按钮
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  '2xl': 24,
};
