// 按字取笔画数据：打包子集（hanziIndex）→ 本地缓存（AsyncStorage）→ 网站下载并缓存。
// 下载失败抛错，调用方（手写判分、笔顺动画）回退或静默。
import { getLocal, setLocal } from './storage';
import type { CharacterData } from './handwriting';
import { bundledHanzi } from './hanziIndex';

// 与网站同域名（Flask 的 CORS 已放行），按需下载没打包的字
const DOWNLOAD_BASE = 'https://learnchinese.kzwbelieve.top/hanzi-data';
const CACHE_PREFIX = 'hanziData:';

const cache = new Map<string, Promise<CharacterData>>();

const readCache = async (char: string): Promise<CharacterData | null> => {
  const raw = await getLocal(CACHE_PREFIX + char);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CharacterData;
  } catch {
    return null;
  }
};

const writeCache = async (char: string, data: CharacterData) => {
  await setLocal(CACHE_PREFIX + char, JSON.stringify(data));
};

const downloadFromWeb = async (char: string): Promise<CharacterData> => {
  const resp = await fetch(`${DOWNLOAD_BASE}/${encodeURIComponent(char)}.json`);
  if (!resp.ok) throw new Error(`no stroke data for ${char}`);
  const data = (await resp.json()) as CharacterData;
  await writeCache(char, data);
  return data;
};

export const loadCharacterData = (char: string): Promise<CharacterData> => {
  if (!cache.has(char)) {
    const request = (async () => {
      // 1. 打包子集（离线可用）
      if (bundledHanzi[char]) return bundledHanzi[char];
      // 2. 本地缓存（此前下载过的字）
      const cached = await readCache(char);
      if (cached) return cached;
      // 3. 网站下载并缓存
      return downloadFromWeb(char);
    })();
    request.catch(() => cache.delete(char));
    cache.set(char, request);
  }
  return cache.get(char)!;
};
