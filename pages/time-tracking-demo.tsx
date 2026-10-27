/**
 * 时间追踪功能演示页面
 * 用于测试和展示时间追踪系统的功能
 */

import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { useRouter } from 'next/router';
import { useComprehensiveTracking } from '@/hooks/useTimeTracking';
import { useLearningContext } from '@/src/context/LearningContext';

export default function TimeTrackingDemo() {
  const [selectedOption, setSelectedOption] = useState('');
  const [demoStartTime] = useState(new Date());
  const [actionCount, setActionCount] = useState(0);
  const router = useRouter();
  // 用当前身份上报：后端只允许为自己创建会话，写死的 demo_user 会被拒绝
  const { userId } = useLearningContext();

  // 时间追踪配置
  const tracking = useComprehensiveTracking({
    userId,
    wordId: 999, // 演示词汇ID
    moduleType: 'demo',
    sessionType: 'test'
  });

  useEffect(() => {
    // 页面加载事件
    tracking.pageTracking.trackPageEnter('time-tracking-demo');
    tracking.trackEvent('demo_start', 'demo-page', {
      startTime: demoStartTime.toISOString(),
      userAgent: navigator.userAgent
    });

    return () => {
      tracking.pageTracking.trackPageLeave('time-tracking-demo');
    };
  }, []);

  const handleTestEvent = (eventType: string) => {
    setActionCount(prev => prev + 1);
    tracking.trackEvent(eventType, 'demo-button', {
      actionNumber: actionCount + 1,
      timestamp: new Date().toISOString()
    });
  };

  const handleTestExercise = async () => {
    // 模拟练习数据
    const mockExerciseData = {
      questionId: 'demo_question_1',
      questionType: 'definition',
      questionContent: 'Test question for demo',
      userAnswer: 'demo_answer',
      correctAnswer: 'demo_answer',
      isCorrect: true,
      startTime: new Date(Date.now() - 5000), // 5秒前开始
      endTime: new Date(),
      hesitationCount: 0,
      confidenceLevel: 5
    };

    await tracking.trackExercise(mockExerciseData);
    handleTestEvent('mock_exercise_completed');
  };

  const handleEndDemo = async () => {
    tracking.trackEvent('demo_end', 'demo-page', {
      totalActions: actionCount,
      duration: Date.now() - demoStartTime.getTime()
    });
    
    await tracking.endSession(true);
    alert('演示会话已结束！请检查控制台日志。');
  };

  const handleOptionChange = (value: string) => {
    tracking.interactionTracking.trackSelectionChange('demo-radio', selectedOption, value);
    setSelectedOption(value);
  };

  const handleAudioTest = () => {
    tracking.interactionTracking.trackAudioPlay('demo-audio', 'test-audio');
    handleTestEvent('audio_test_played');
  };

  const sessionInfo = tracking.sessionInfo;

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-4xl mx-auto space-y-6">
        
        {/* 页面标题 */}
        <Card>
          <CardHeader>
            <CardTitle>🕒 时间追踪系统演示</CardTitle>
            <CardDescription>
              测试学习时间追踪和用户行为记录功能
            </CardDescription>
          </CardHeader>
        </Card>

        {/* 会话信息卡片 */}
        <Card>
          <CardHeader>
            <CardTitle>📊 当前会话信息</CardTitle>
          </CardHeader>
          <CardContent>
            {sessionInfo ? (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <strong>会话ID:</strong> {sessionInfo.sessionId?.slice(-8)}...
                </div>
                <div>
                  <strong>持续时间:</strong> {sessionInfo.duration}秒
                </div>
                <div>
                  <strong>活跃时间:</strong> {sessionInfo.activeDuration}秒
                </div>
                <div>
                  <strong>活跃率:</strong> {(sessionInfo.activeRate * 100).toFixed(1)}%
                </div>
                <div>
                  <strong>事件数量:</strong> {sessionInfo.eventCount}
                </div>
                <div>
                  <strong>当前状态:</strong> {sessionInfo.isActive ? '活跃' : '非活跃'}
                </div>
              </div>
            ) : (
              <p>会话信息加载中...</p>
            )}
          </CardContent>
        </Card>

        {/* 交互测试区域 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* 按钮测试 */}
          <Card>
            <CardHeader>
              <CardTitle>🔘 按钮点击测试</CardTitle>
              <CardDescription>测试按钮交互事件记录</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button 
                onClick={() => handleTestEvent('button_click_test')}
                className="w-full"
              >
                测试按钮点击 (已点击 {actionCount} 次)
              </Button>
              
              <Button 
                onClick={handleAudioTest}
                variant="outline"
                className="w-full"
              >
                测试音频播放事件
              </Button>
              
              <Button 
                onClick={handleTestExercise}
                variant="secondary"
                className="w-full"
              >
                模拟练习记录
              </Button>
            </CardContent>
          </Card>

          {/* 选择测试 */}
          <Card>
            <CardHeader>
              <CardTitle>📝 选择事件测试</CardTitle>
              <CardDescription>测试选项变更事件记录</CardDescription>
            </CardHeader>
            <CardContent>
              <RadioGroup value={selectedOption} onValueChange={handleOptionChange} className="space-y-2">
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="option1" id="option1" />
                  <Label htmlFor="option1">选项 1 - 测试选择事件</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="option2" id="option2" />
                  <Label htmlFor="option2">选项 2 - 测试犹豫记录</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="option3" id="option3" />
                  <Label htmlFor="option3">选项 3 - 测试时间记录</Label>
                </div>
              </RadioGroup>
              
              {selectedOption && (
                <div className="mt-3 p-2 bg-blue-100 rounded text-sm">
                  已选择: {selectedOption}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 练习计时器测试 */}
        <Card>
          <CardHeader>
            <CardTitle>⏱️ 练习计时器测试</CardTitle>
            <CardDescription>测试练习题计时功能</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <strong>当前计时:</strong> {tracking.exerciseTimer.getCurrentTimer()}秒
              </div>
              <div>
                <strong>犹豫次数:</strong> {tracking.exerciseTimer.hesitationCount}
              </div>
              <div>
                <strong>已答题:</strong> {tracking.exerciseTimer.isAnswered ? '是' : '否'}
              </div>
            </div>
            
            <div className="flex gap-2 mt-4">
              <Button 
                onClick={tracking.exerciseTimer.startTimer}
                size="sm"
              >
                开始计时
              </Button>
              <Button 
                onClick={tracking.exerciseTimer.recordHesitation}
                size="sm"
                variant="outline"
              >
                记录犹豫
              </Button>
              <Button 
                onClick={tracking.exerciseTimer.submitAnswer}
                size="sm"
                variant="secondary"
              >
                提交答案
              </Button>
            </div>
            
            {tracking.exerciseTimer.isAnswered && (
              <div className="mt-3 p-2 bg-green-100 rounded text-sm">
                响应时间: {tracking.exerciseTimer.getResponseTime().toFixed(1)}秒
              </div>
            )}
          </CardContent>
        </Card>

        {/* 控制区域 */}
        <Card>
          <CardHeader>
            <CardTitle>🎮 控制面板</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Button 
                onClick={() => router.push('/word-learning-entrance')}
                variant="outline"
              >
                前往学习入口
              </Button>
              <Button 
                onClick={() => router.push('/exercise')}
                variant="outline"
              >
                前往练习页面
              </Button>
            </div>
            
            <Button 
              onClick={handleEndDemo}
              variant="destructive"
              className="w-full"
            >
              结束演示会话
            </Button>
          </CardContent>
        </Card>

        {/* 说明信息 */}
        <Card>
          <CardHeader>
            <CardTitle>📋 功能说明</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm space-y-2">
              <p><strong>时间追踪:</strong> 自动记录页面停留时间、活跃时间、响应时间等</p>
              <p><strong>行为记录:</strong> 记录点击、选择、音频播放等所有用户交互</p>
              <p><strong>练习分析:</strong> 详细记录答题过程、犹豫次数、正确率等</p>
              <p><strong>会话管理:</strong> 完整的学习会话生命周期管理</p>
              <p><strong>数据同步:</strong> 实时或批量同步数据到后端API</p>
            </div>
            
            <div className="mt-4 p-3 bg-yellow-100 rounded text-sm">
              <strong>💡 提示:</strong> 打开浏览器控制台查看详细的追踪日志输出
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
