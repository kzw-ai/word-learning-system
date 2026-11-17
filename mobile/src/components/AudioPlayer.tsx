// 源文件：components/AudioPlayer.tsx（网页版）。RN 版：expo-audio 放音频文件，expo-speech 朗读。
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import * as Speech from 'expo-speech';
import { buildApiUrl } from '@/lib/apiClient';
import { colors, radius } from '@/theme';

interface AudioPlayerProps {
  text: string;
  /** 后端音频文件地址（相对路径，如 /api/audio/xxx.mp3）；没有则直接朗读 */
  audioUrl?: string;
  language?: string;
  onPlay?: () => void;
  onEnd?: () => void;
  onError?: (error: Error) => void;
}

const FILE_LOAD_TIMEOUT_MS = 3000;

/**
 * 发音按钮：先放后端音频文件；文件取不到（404/格式不支持）才用系统朗读（expo-speech，
 * zh-CN、rate 0.9）。一次播放最多回退一次；旧播放晚到的错误不打断新播放（attemptRef/fellBackRef）。
 * 文件播放的状态由 status.playing / didJustFinish / error 驱动。
 */
export default function AudioPlayer({ text, audioUrl, language = 'zh-CN', onPlay, onEnd, onError }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [speechMode, setSpeechMode] = useState(false);
  const attemptRef = useRef(0);
  const fellBackRef = useRef(-1);
  const mountedRef = useRef(true);
  const onPlayFiredRef = useRef(false);
  const onPlayRef = useRef(onPlay);
  onPlayRef.current = onPlay;
  const onEndRef = useRef(onEnd);
  onEndRef.current = onEnd;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const fileSource = audioUrl ? buildApiUrl(audioUrl) : null;
  const player = useAudioPlayer();
  const status = useAudioPlayerStatus(player);
  const statusRef = useRef(status);
  statusRef.current = status;

  // 卸载后：迟到的媒体事件不能再朗读（会读出上一页内容）；停掉文件和朗读
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      attemptRef.current += 1;
      Speech.stop();
      try {
        player.pause();
      } catch {
        /* 已卸载 */
      }
    };
  }, [player]);

  const speak = useCallback(
    (attempt: number) => {
      Speech.stop();
      Speech.speak(text, {
        language,
        rate: 0.9,
        onStart: () => {
          if (!mountedRef.current || attempt !== attemptRef.current) return;
          setIsPlaying(true);
          setIsLoading(false);
          setSpeechMode(true);
          onPlayRef.current?.();
        },
        onDone: () => {
          if (!mountedRef.current || attempt !== attemptRef.current) return;
          setIsPlaying(false);
          setSpeechMode(false);
          onEndRef.current?.();
        },
        onStopped: () => {
          if (!mountedRef.current || attempt !== attemptRef.current) return;
          setIsPlaying(false);
          setSpeechMode(false);
        },
        onError: () => {
          if (!mountedRef.current || attempt !== attemptRef.current) return;
          setIsPlaying(false);
          setIsLoading(false);
          setSpeechMode(false);
          setHasError(true);
          onErrorRef.current?.(new Error('Speech synthesis failed'));
        },
      });
    },
    [text, language]
  );

  const fallBackToSpeech = useCallback(
    (attempt: number, cause: unknown) => {
      if (!mountedRef.current || attempt !== attemptRef.current || fellBackRef.current === attempt) return;
      fellBackRef.current = attempt;
      console.warn('Audio file unavailable, using speech synthesis instead:', cause);
      speak(attempt);
    },
    [speak]
  );

  // 文件播放状态驱动：开始播放时收起 loading、置播放中并 onPlay；自然播完复位
  useEffect(() => {
    if (!mountedRef.current || speechMode) return;
    if (status.playing) {
      setIsLoading(false);
      setIsPlaying(true);
      if (!onPlayFiredRef.current) {
        onPlayFiredRef.current = true;
        onPlayRef.current?.();
      }
    } else if (status.didJustFinish) {
      setIsPlaying(false);
      setIsLoading(false);
      onPlayFiredRef.current = false;
      onEndRef.current?.();
    }
  }, [status.playing, status.didJustFinish, speechMode]);

  // 文件加载失败（status.error 有值）→ 停掉文件、回退朗读
  useEffect(() => {
    if (!mountedRef.current || speechMode) return;
    if (status.error && !status.playing && !status.didJustFinish) {
      try {
        player.pause();
      } catch {
        /* 没在放文件 */
      }
      fallBackToSpeech(attemptRef.current, new Error(status.error));
    }
  }, [status.error, speechMode, fallBackToSpeech, player]);

  const handlePlay = () => {
    if (isPlaying) {
      // 播放中再点一下 = 停止（文件和朗读都停）
      try {
        player.pause();
      } catch {
        /* 没在放文件 */
      }
      Speech.stop();
      setIsPlaying(false);
      setSpeechMode(false);
      onPlayFiredRef.current = false;
      return;
    }

    attemptRef.current += 1;
    const attempt = attemptRef.current;
    setIsLoading(true);
    setHasError(false);
    setSpeechMode(false);
    onPlayFiredRef.current = false;

    if (fileSource) {
      try {
        player.replace(fileSource);
        player.play();
        // 兜底超时：status.error 可能不触发（网络慢等），超时还没加载出来就回退
        setTimeout(() => {
          const s = statusRef.current;
          if (mountedRef.current && attempt === attemptRef.current && !s.playing && !s.isLoaded && !s.error) {
            try {
              player.pause();
            } catch {
              /* ignore */
            }
            fallBackToSpeech(attempt, new Error('Audio file failed to load'));
          }
        }, FILE_LOAD_TIMEOUT_MS);
      } catch (error) {
        fallBackToSpeech(attempt, error);
      }
    } else {
      speak(attempt);
    }
  };

  return (
    <Pressable
      style={[styles.btn, isLoading && styles.btnLoading]}
      onPress={handlePlay}
      hitSlop={6}
      accessibilityLabel={isPlaying ? 'Stop audio' : 'Play audio'}
      accessibilityRole="button"
    >
      {isLoading ? (
        <ActivityIndicator size="small" color={colors.white} />
      ) : (
        <Text style={[styles.icon, isPlaying && styles.iconPlaying, hasError && styles.iconError]}>
          {isPlaying ? '■' : hasError ? '✕' : '🔊'}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    minWidth: 36,
    minHeight: 36,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // 加载中转圈用白底深色圆点，绿底上也看得见
  btnLoading: { backgroundColor: 'rgba(0,0,0,0.18)' },
  icon: { fontSize: 18, color: colors.textFaint },
  iconPlaying: { color: colors.primary },
  iconError: { color: colors.dangerText },
});
