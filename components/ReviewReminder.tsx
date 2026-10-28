import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buildApiUrl } from "@/src/lib/apiClient";
import { Clock, X } from 'lucide-react';

interface ReviewReminderProps {
  userId: string;
  showInline?: boolean;
}

const ReviewReminder: React.FC<ReviewReminderProps> = ({ userId, showInline = false }) => {
  const router = useRouter();
  const [dueCount, setDueCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!userId) return;
    fetchDueReviews();
  }, [userId]);

  const fetchDueReviews = async () => {
    try {
      setLoading(true);
      const response = await fetch(buildApiUrl(`/api/review/user/${userId}/due?limit=1`));
      const result = await response.json();

      if (response.ok && result.success) {
        setDueCount(result.data.length);
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
          <p className="text-xs mb-2">
            You have <Badge className="bg-white text-red-600 mx-1">{dueCount}</Badge> {dueCount === 1 ? 'word' : 'words'} to review
          </p>
          <Button
            size="sm"
            onClick={handleGoToReview}
            className="w-full bg-white text-red-600 hover:bg-gray-100 text-xs"
          >
            Review now
          </Button>
        </div>
      </div>
    );
  }

  // 内嵌提醒样式
  return (
    <div className="bg-gradient-to-r from-red-50 to-orange-50 border border-red-300 rounded-lg p-2 mb-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center flex-1">
          <Clock size={14} className="mr-1 text-red-600" />
          <span className="text-xs text-red-800">
            <span className="font-bold">{dueCount}</span> {dueCount === 1 ? 'word' : 'words'} due
          </span>
        </div>
        <Button
          size="sm"
          onClick={handleGoToReview}
          className="bg-red-500 hover:bg-red-600 text-white text-xs px-2 py-1 h-auto"
        >
          Review
        </Button>
      </div>
    </div>
  );
};

export default ReviewReminder;

