// 源文件：components/AudioPlayer.tsx（网页版）。RN 版：expo-audio 放音频文件，expo-speech 朗读。
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from 'expo-audio';
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
 */
export default function AudioPlayer({ text, audioUrl, language = 'zh-CN', onPlay, onEnd, onError }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [speechMode, setSpeechMode] = useState(false);
  // 每点一次播放记一个编号：文件加载失败和 play() 的失败可能先后到达，同一次播放只回退一次；
  // 旧编号的迟到回调、组件卸载后的回调都不再起作用
  const attemptRef = useRef(0);
  const fellBackRef = useRef(-1);
  const mountedRef = useRef(true);

  const fileSource = audioUrl ? buildApiUrl(audioUrl) : null;
  const player = useAudioPlayer();
  const status = useAudioPlayerStatus(player);
  const statusRef = useRef(status);
  statusRef.current = status;

  // 音频会话：iOS 静音键打开时也要出声（playsInSilentMode）
  useEffect(() => {
    setAudioModeAsync({ playsInSilentMode: true }).catch(() => {});
  }, []);

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

  // 文件播放自然结束
  useEffect(() => {
    if (status.didJustFinish && !speechMode && mountedRef.current) {
      setIsPlaying(false);
      onEnd?.();
    }
  }, [status.didJustFinish, speechMode, onEnd]);

  const speak = (attempt: number) => {
    Speech.stop();
    Speech.speak(text, {
      language,
      rate: 0.9,
      onStart: () => {
        if (!mountedRef.current || attempt !== attemptRef.current) return;
        setIsPlaying(true);
        setIsLoading(false);
        setSpeechMode(true);
        onPlay?.();
      },
      onDone: () => {
        if (!mountedRef.current) return;
        setIsPlaying(false);
        setSpeechMode(false);
        onEnd?.();
      },
      onStopped: () => {
        if (!mountedRef.current) return;
        setIsPlaying(false);
        setSpeechMode(false);
      },
      onError: () => {
        if (!mountedRef.current) return;
        setIsPlaying(false);
        setIsLoading(false);
        setSpeechMode(false);
        setHasError(true);
        onError?.(new Error('Speech synthesis failed'));
      },
    });
  };

  const fallBackToSpeech = (attempt: number, cause: unknown) => {
    if (!mountedRef.current || attempt !== attemptRef.current || fellBackRef.current === attempt) return;
    fellBackRef.current = attempt;
    console.warn('Audio file unavailable, using speech synthesis instead:', cause);
    speak(attempt);
  };

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
      return;
    }

    attemptRef.current += 1;
    const attempt = attemptRef.current;
    setIsLoading(true);
    setHasError(false);
    setSpeechMode(false);

    if (fileSource) {
      try {
        player.replace(fileSource);
        player.play();
        // 文件取不到（还没部署、404、格式不支持）：超时没加载出来就回退朗读
        setTimeout(() => {
          const s = statusRef.current;
          if (mountedRef.current && attempt === attemptRef.current && !s.isLoaded && !s.playing) {
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
      style={styles.btn}
      onPress={handlePlay}
      hitSlop={6}
      accessibilityLabel={isPlaying ? 'Stop audio' : 'Play audio'}
    >
      {isLoading ? (
        <ActivityIndicator size="small" color={colors.textFaint} />
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
  icon: { fontSize: 18, color: colors.textFaint },
  iconPlaying: { color: colors.primary },
  iconError: { color: colors.dangerText },
});
