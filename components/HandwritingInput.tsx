import React, { useRef, useState, useEffect } from 'react';
import SignatureCanvas from 'react-signature-canvas';
import { Button } from '@/components/ui/button';
import { Eraser, RotateCcw, Check, X } from 'lucide-react';

interface HandwritingInputProps {
  onSubmit: (text: string) => void;
  onCancel?: () => void;
  placeholder?: string;
  width?: number;
  height?: number;
}

/**
 * 手写输入组件
 * 支持：
 * 1. Canvas手写输入
 * 2. 清除/重写功能
 * 3. 简单的笔画识别（基于Canvas数据）
 * 4. 键盘输入备选
 */
export default function HandwritingInput({
  onSubmit,
  onCancel,
  placeholder = 'Write or type here',
  width = 300,
  height = 150,
}: HandwritingInputProps) {
  const signatureRef = useRef<SignatureCanvas>(null);
  const [isEmpty, setIsEmpty] = useState(true);
  const [useKeyboard, setUseKeyboard] = useState(false);
  const [keyboardInput, setKeyboardInput] = useState('');

  useEffect(() => {
    // 检查Canvas是否为空
    const checkEmpty = () => {
      if (signatureRef.current) {
        const canvas = signatureRef.current.getCanvas();
        const ctx = canvas.getContext('2d');
        if (ctx) {
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const hasContent = imageData.data.some((pixel) => pixel !== 0);
          setIsEmpty(!hasContent);
        }
      }
    };

    // 监听绘制事件
    const interval = setInterval(checkEmpty, 300);
    return () => clearInterval(interval);
  }, []);

  const handleClear = () => {
    if (signatureRef.current) {
      signatureRef.current.clear();
      setIsEmpty(true);
    }
  };

  const handleSubmit = () => {
    if (useKeyboard) {
      // 键盘输入模式
      if (keyboardInput.trim()) {
        onSubmit(keyboardInput.trim());
        setKeyboardInput('');
      }
    } else {
      // 手写模式 - 简化版：让用户自己录入所写内容
      // 在实际应用中，这里应该调用OCR API
      if (!isEmpty) {
        // 注意：绝不能把正确答案作为默认值预填，否则用户直接确认即判对，
        // 填空题将不再采集任何有效作答信号（is_correct 恒为 true）。
        const userInput = prompt('Type what you just wrote:');
        if (userInput && userInput.trim()) {
          onSubmit(userInput.trim());
          handleClear();
        }
      }
    }
  };

  const handleToggleInput = () => {
    setUseKeyboard(!useKeyboard);
    if (!useKeyboard) {
      handleClear();
    } else {
      setKeyboardInput('');
    }
  };

  return (
    <div className="flex flex-col items-center mt-4">
      <div
        className="bg-gray-200 rounded-sm overflow-hidden mb-4"
        style={{ width: `${width}px`, height: `${height}px` }}
      >
        <SignatureCanvas
          ref={signatureRef}
          canvasProps={{
            width: width,
            height: height,
            className: 'w-full h-full',
          }}
          backgroundColor="transparent"
          penColor="black"
          minWidth={2}
          maxWidth={4}
          onEnd={() => setIsEmpty(false)}
        />
      </div>

      <div className="flex w-full gap-3 justify-center" style={{ width: `${width}px` }}>
        <Button
          variant="outline"
          onClick={handleClear}
          className="flex-1 h-10 rounded-md border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 text-[15px] font-medium"
        >
          Rewrite
        </Button>
        <Button
          onClick={handleSubmit}
          className="flex-1 h-10 rounded-md border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 text-[15px] font-medium shadow-sm"
        >
          Finish
        </Button>
      </div>
    </div>
  );
}

/**
 * 简化版手写输入（内联样式）
 */
export function InlineHandwritingInput({
  onSubmit,
  placeholder = 'Write or type',
}: {
  onSubmit: (text: string) => void;
  placeholder?: string;
}) {
  const [value, setValue] = useState('');

  const handleSubmit = () => {
    if (value.trim()) {
      onSubmit(value.trim());
      setValue('');
    }
  };

  return (
    <div className="flex gap-2 items-center">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyPress={(e) => {
          if (e.key === 'Enter') {
            handleSubmit();
          }
        }}
        placeholder={placeholder}
        className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <Button
        size="sm"
        onClick={handleSubmit}
        disabled={!value.trim()}
        className="bg-blue-500 hover:bg-blue-600"
      >
        <Check size={14} />
      </Button>
    </div>
  );
}

