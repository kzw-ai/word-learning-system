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

  useEffect(() => {
    if (autoPlay) {
      handlePlay();
    }
  }, [autoPlay, text]);

  // 清理
  useEffect(() => {
    return () => {
      if (synthRef.current && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      if (audioRef.current) {
        audioRef.current.pause();
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

      audioRef.current.onerror = () => {
        setIsPlaying(false);
        setIsLoading(false);
        setHasError(true);
        const error = new Error('Failed to load audio');
        onError?.(error);
      };
    }

    audioRef.current.play().catch((error) => {
      setIsPlaying(false);
      setIsLoading(false);
      setHasError(true);
      onError?.(error);
      console.error('Audio play error:', error);
    });
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
      className={`
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

