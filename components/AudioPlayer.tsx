import React, { useState, useRef, useEffect } from 'react';
import { Volume2, VolumeX, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface AudioPlayerProps {
  text: string;
  audioUrl?: string;
  language?: string;
  autoPlay?: boolean;
  showButton?: boolean;
  buttonSize?: 'sm' | 'md' | 'lg';
  onPlay?: () => void;
  onEnd?: () => void;
  onError?: (error: Error) => void;
}

/**
 * 通用音频播放器组件
 * 支持：
 * 1. Web Speech API (TTS) - 免费，无需音频文件
 * 2. 预录音频文件 - 高质量，需要音频资源
 * 3. 外部TTS服务 - 可选，需要API密钥
 */
export default function AudioPlayer({
  text,
  audioUrl,
  language = 'zh-CN',
  autoPlay = false,
  showButton = true,
  buttonSize = 'md',
  onPlay,
  onEnd,
  onError,
}: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const synthRef = useRef<SpeechSynthesisUtterance | null>(null);
  // 每点一次播放记一个编号：文件的 error 事件和 play() 的失败可能先后到达，同一次播放只回退一次；
  // 旧编号的迟到回调、组件卸载后的回调都不再起作用
  const attemptRef = useRef(0);
  const fellBackRef = useRef(-1);
  const mountedRef = useRef(true);

  useEffect(() => {
    if (autoPlay) {
      handlePlay();
    }
  }, [autoPlay, text]);

  // 同一个按钮换了地址（换题后同一位置的选项）：丢掉旧的音频，下次播放按新地址重建
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        const audio = audioRef.current;
        audio.oncanplay = audio.onplay = audio.onended = audio.onerror = null;
        audio.pause();
        audioRef.current = null;
        setIsPlaying(false);
      }
    };
  }, [audioUrl]);

  // 清理：卸载后迟到的媒体事件不能再去朗读（会读出上一页的内容、打断新页面的朗读）
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      attemptRef.current += 1;
      if (synthRef.current && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      if (audioRef.current) {
        const audio = audioRef.current;
        audio.oncanplay = audio.onplay = audio.onended = audio.onerror = null;
        audio.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const playWithWebSpeech = () => {
    if (!window.speechSynthesis) {
      throw new Error('Speech synthesis is not supported in this browser');
    }

    // 停止当前播放
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language;
    utterance.rate = 0.9; // 稍微慢一点，更清晰
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    utterance.onstart = () => {
      setIsPlaying(true);
      setIsLoading(false);
      onPlay?.();
    };

    utterance.onend = () => {
      setIsPlaying(false);
      onEnd?.();
    };

    utterance.onerror = (event) => {
      // 我们自己取消的（又点了一次、换成另一段朗读、离开页面）不算失败
      if (!mountedRef.current || event.error === 'canceled' || event.error === 'interrupted') {
        if (mountedRef.current) {
          // 还没开始就被取消（页面上另一个按钮开始朗读）时 onstart 不会来：在这里收起加载状态，按钮还能再点
          setIsPlaying(false);
          setIsLoading(false);
        }
        return;
      }
      setIsPlaying(false);
      setIsLoading(false);
      setHasError(true);
      const error = new Error(`Speech synthesis failed: ${event.error}`);
      onError?.(error);
      console.error('Speech synthesis error:', event);
    };

    synthRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  };

  const playWithAudioFile = () => {
    if (!audioUrl) {
      throw new Error('No audio URL provided');
    }

    const attempt = attemptRef.current;
    if (!audioRef.current) {
      audioRef.current = new Audio(audioUrl);
      
      audioRef.current.oncanplay = () => {
        setIsLoading(false);
      };

      audioRef.current.onplay = () => {
        setIsPlaying(true);
        onPlay?.();
      };

      audioRef.current.onended = () => {
        setIsPlaying(false);
        onEnd?.();
      };

    }
    // 文件取不到（还没部署到服务器、早期的占位地址）：改用浏览器朗读，按钮不至于失灵。
    // 每次播放重新绑定，记住这是哪一次播放、哪个元素：旧元素迟到的错误不能清掉新元素、再回退一次
    const audio = audioRef.current;
    audio.onerror = () => {
      if (audioRef.current === audio) audioRef.current = null;
      fallBackToSpeech(attempt, new Error('Failed to load audio'));
    };

    audio.play().catch((error) => {
      if (!mountedRef.current || attempt !== attemptRef.current) return;
      // 用户主动打断播放（又点了一次）不算失败
      if (error?.name === 'AbortError') return;
      if (error?.name === 'NotSupportedError') {
        if (audioRef.current === audio) audioRef.current = null;
        fallBackToSpeech(attempt, error);
        return;
      }
      setIsPlaying(false);
      setIsLoading(false);
      setHasError(true);
      onError?.(error);
      console.error('Audio play error:', error);
    });
  };

  const fallBackToSpeech = (attempt: number, cause: Error) => {
    if (!mountedRef.current || attempt !== attemptRef.current || fellBackRef.current === attempt) return;
    fellBackRef.current = attempt;
    console.warn('Audio file unavailable, using speech synthesis instead:', cause.message);
    try {
      playWithWebSpeech();
    } catch (error) {
      setIsPlaying(false);
      setIsLoading(false);
      setHasError(true);
      onError?.(error as Error);
    }
  };

  const handlePlay = async () => {
    if (isPlaying) {
      // 停止播放
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      setIsPlaying(false);
      return;
    }

    attemptRef.current += 1;
    setIsLoading(true);
    setHasError(false);

    try {
      if (audioUrl) {
        // 优先使用音频文件
        playWithAudioFile();
      } else {
        // 使用Web Speech API
        playWithWebSpeech();
      }
    } catch (error) {
      setIsLoading(false);
      setHasError(true);
      console.error('Audio play error:', error);
      onError?.(error as Error);
    }
  };

  if (!showButton) {
    return null;
  }

  const iconSize = buttonSize === 'sm' ? 16 : buttonSize === 'lg' ? 24 : 20;

  return (
    <Button
      variant="ghost"
      size={buttonSize === 'sm' ? 'sm' : 'default'}
      onClick={handlePlay}
      disabled={isLoading}
      // 小号也保证 36px 高，手指点得准
      className={`
        ${buttonSize === 'sm' ? 'h-9 min-w-9 px-2' : ''}
        ${isPlaying ? 'text-blue-500' : hasError ? 'text-red-500' : 'text-gray-500'}
        hover:text-blue-600
        ${isLoading ? 'opacity-50' : ''}
      `}
      title={isPlaying ? 'Stop' : 'Play audio'}
    >
      {isLoading ? (
        <Loader2 size={iconSize} className="animate-spin" />
      ) : hasError ? (
        <VolumeX size={iconSize} />
      ) : (
        <Volume2 size={iconSize} />
      )}
    </Button>
  );
}

/**
 * 简化版音频播放按钮
 */
export function QuickAudioButton({ text, audioUrl }: { text: string; audioUrl?: string }) {
  return <AudioPlayer text={text} audioUrl={audioUrl} buttonSize="sm" />;
}

/**
 * 自动播放音频（不显示按钮）
 */
export function AutoPlayAudio({ text, audioUrl }: { text: string; audioUrl?: string }) {
  return (
    <AudioPlayer 
      text={text} 
      audioUrl={audioUrl} 
      autoPlay={true} 
      showButton={false} 
    />
  );
}

