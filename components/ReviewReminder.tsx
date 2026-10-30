import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buildApiUrl } from "@/src/lib/apiClient";
import { Clock, X } from 'lucide-react';

interface ReviewReminderProps {
  userId: string;
  showInline?: boolean;
  /** 正在学的词：练到一半时它也算「到期」（好让中途退出后能接着练），不该提醒学习者去复习它 */
  currentWordId?: number | null;
}

const ReviewReminder: React.FC<ReviewReminderProps> = ({ userId, showInline = false, currentWordId = null }) => {
  const router = useRouter();
  const [dueCount, setDueCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!userId) return;
    fetchDueReviews();
  }, [userId, currentWordId]);

  const fetchDueReviews = async () => {
    try {
      setLoading(true);
      // 要数个数，不能只取 1 条（以前 limit=1，几个词到期都显示「1 个」）
      const response = await fetch(buildApiUrl(`/api/review/user/${userId}/due?limit=100`));
      const result = await response.json();

      if (response.ok && result.success) {
        setDueCount(result.data.filter((review: { word_id: number }) => review.word_id !== currentWordId).length);
      }
    } catch (err) {
      console.error('获取复习提醒失败:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleGoToReview = () => {
    router.push('/today-review');
  };

  const handleDismiss = () => {
    setDismissed(true);
  };

  if (loading || dueCount === 0 || dismissed) {
    return null;
  }

  // 浮动提醒样式
  if (!showInline) {
    return (
      <div className="fixed top-16 right-4 z-50 animate-slide-in">
        <div className="bg-gradient-to-r from-red-500 to-orange-500 text-white rounded-lg shadow-lg p-3 max-w-xs">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center">
              <Clock size={18} className="mr-2 animate-pulse" />
              <span className="font-semibold text-sm">Review reminder</span>
            </div>
            <button 
              onClick={handleDismiss}
              className="text-white hover:text-gray-200"
            >
              <X size={16} />
            </button>
          </div>
          <p className="text-sm mb-2">
            You have <Badge className="bg-white text-red-600 mx-1">{dueCount}</Badge> {dueCount === 1 ? 'word' : 'words'} to review
          </p>
          <Button
            size="sm"
            onClick={handleGoToReview}
            className="w-full h-9 bg-white text-rose-700 hover:bg-rose-50 text-sm font-semibold"
          >
            Review now
          </Button>
        </div>
      </div>
    );
  }

  // 内嵌提醒样式
  return (
    <div className="bg-rose-50 border border-rose-200 rounded-xl px-3 py-2 mb-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center flex-1">
          <Clock size={16} className="mr-1.5 text-rose-700" aria-hidden="true" />
          <span className="text-sm text-rose-800">
            <span className="font-bold">{dueCount}</span> {dueCount === 1 ? 'word' : 'words'} due
          </span>
        </div>
        <Button
          size="sm"
          onClick={handleGoToReview}
          className="bg-rose-600 hover:bg-rose-700 text-white text-sm font-semibold px-3 h-9 rounded-lg"
        >
          Review
        </Button>
      </div>
    </div>
  );
};

export default ReviewReminder;

