import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { authenticatedFetch } from "@/src/lib/authClient";

const LearningStats = () => {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await authenticatedFetch('/api/stats');
      const result = await response.json();
      
      if (response.ok) {
        setStats(result.data);
      } else {
        setError('API服务未运行');
      }
    } catch (err) {
      setError('无法连接到API服务');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex flex-col font-sans items-center justify-center">
        <div className="w-full max-w-md mx-auto bg-white/40 backdrop-blur-xl border border-white/60 shadow-2xl relative min-h-[844px] flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mb-4"></div>
          <p className="text-gray-600 text-sm">Loading stats...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex flex-col font-sans items-center justify-center">
        <div className="w-full max-w-md mx-auto bg-white/40 backdrop-blur-xl border border-white/60 shadow-2xl relative min-h-[844px] flex flex-col items-center justify-center px-6">
          <div className="glass-card w-full p-6 text-center rounded-2xl border border-red-200 bg-red-50/50">
            <p className="text-red-600 mb-4 font-medium">❌ {error}</p>
            <Button 
                onClick={() => window.location.reload()}
                className="w-full bg-red-500 hover:bg-red-600 text-white rounded-xl shadow-lg shadow-red-500/20"
            >
                Reload
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex flex-col font-sans">
      <div className="w-full max-w-md mx-auto bg-white/40 backdrop-blur-xl border border-white/60 shadow-2xl overflow-hidden relative min-h-[844px] flex flex-col">
        
        {/* Header */}
        <div className="px-6 pt-12 pb-6 border-b border-white/30 bg-white/20 text-center">
          <h1 className="text-2xl font-bold flex items-center justify-center text-indigo-950">
            📊 Learning Stats
          </h1>
          <p className="text-xs text-indigo-600 font-medium mt-1">
            System Data Overview
          </p>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4 pb-24">
          {stats && (
            <>
              {/* KPIs Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-card p-4 text-center rounded-2xl border border-white/60 bg-white/40">
                  <div className="text-2xl mb-1">📚</div>
                  <div className="text-xl font-bold text-indigo-950">{stats.totalSessions}</div>
                  <div className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mt-1">Sessions</div>
                </div>

                <div className="glass-card p-4 text-center rounded-2xl border border-white/60 bg-white/40">
                  <div className="text-2xl mb-1">✏️</div>
                  <div className="text-xl font-bold text-indigo-950">{stats.totalExercises}</div>
                  <div className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mt-1">Exercises</div>
                </div>

                <div className="glass-card p-4 text-center rounded-2xl border border-white/60 bg-white/40">
                  <div className="text-2xl mb-1">📈</div>
                  <div className="text-xl font-bold text-indigo-950">{(stats.averageMastery * 100).toFixed(1)}%</div>
                  <div className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mt-1">Avg Mastery</div>
                </div>

                <div className="glass-card p-4 text-center rounded-2xl border border-white/60 bg-white/40">
                  <div className="text-2xl mb-1">⚡</div>
                  <div className="text-xl font-bold text-indigo-950">{stats.averageEfficiency.toFixed(1)}</div>
                  <div className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mt-1">Efficiency</div>
                </div>
              </div>

              {/* Engine Status */}
              <div className="glass-card p-5 rounded-2xl border border-white/60 bg-white/40">
                <div className="flex flex-col mb-4">
                  <h3 className="font-bold text-indigo-950 flex items-center mb-3">
                    🧠 Engine Status
                  </h3>
                  <div className="flex space-x-2">
                    <span className={`text-[10px] px-2 py-1 rounded-full font-semibold ${stats.adaptiveEngine ? "bg-emerald-100 text-emerald-700 border border-emerald-200" : "bg-gray-100 text-gray-500"}`}>
                      {stats.adaptiveEngine ? "✅ Adaptive" : "❌ Adaptive"}
                    </span>
                    <span className={`text-[10px] px-2 py-1 rounded-full font-semibold ${stats.spacedRepetition ? "bg-emerald-100 text-emerald-700 border border-emerald-200" : "bg-gray-100 text-gray-500"}`}>
                      {stats.spacedRepetition ? "✅ Spaced Repetition" : "❌ Spaced Repetition"}
                    </span>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <h4 className="font-semibold text-xs text-indigo-500 uppercase tracking-wider mb-2">📊 Data Stats</h4>
                    <ul className="space-y-1.5 text-sm">
                      <li className="flex justify-between items-center text-gray-600">
                        <span>Recent Sessions:</span>
                        <span className="font-bold text-indigo-950">{stats.recentSessions}</span>
                      </li>
                      <li className="flex justify-between items-center text-gray-600">
                        <span>Progress Records:</span>
                        <span className="font-bold text-indigo-950">{stats.progressRecords}</span>
                      </li>
                    </ul>
                  </div>
                  <div className="pt-2 border-t border-indigo-50/50">
                    <h4 className="font-semibold text-xs text-emerald-500 uppercase tracking-wider mb-2 mt-2">🎯 Active Features</h4>
                    <ul className="space-y-1.5 text-[13px] text-gray-600">
                      <li className="flex items-center gap-2">
                        <div className={`w-1.5 h-1.5 rounded-full ${stats.adaptiveEngine ? 'bg-emerald-500' : 'bg-gray-300'}`}></div>
                        Adaptive Recommendation
                      </li>
                      <li className="flex items-center gap-2">
                        <div className={`w-1.5 h-1.5 rounded-full ${stats.spacedRepetition ? 'bg-emerald-500' : 'bg-gray-300'}`}></div>
                        Spaced Repetition tracking
                      </li>
                      <li className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                        Learning Data Analytics
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Suggestions */}
              <div className="glass-card p-5 rounded-2xl border border-white/60 bg-white/40">
                <h3 className="font-bold text-indigo-950 flex items-center mb-3">
                  💡 Suggestions
                </h3>
                <div className="space-y-3">
                  <div className="p-3 bg-indigo-50/80 rounded-xl border border-indigo-100">
                    <h4 className="font-semibold text-indigo-800 text-sm mb-1">🎯 Start Learning</h4>
                    <p className="text-xs text-indigo-700/80 leading-relaxed">
                      Click "Start Learning" to experience the VKS assessment and personalized path.
                    </p>
                  </div>
                  <div className="p-3 bg-emerald-50/80 rounded-xl border border-emerald-100">
                    <h4 className="font-semibold text-emerald-800 text-sm mb-1">📊 Demo</h4>
                    <p className="text-xs text-emerald-700/80 leading-relaxed">
                      Visit "Phase 2 Demo" to explore the engine internals.
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Bottom Navigation */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-white/40 backdrop-blur-xl border-t border-white/50">
          <div className="flex gap-2">
            <Button 
                variant="outline" 
                onClick={() => router.push('/')}
                className="flex-1 bg-white/60 border-white/80 hover:bg-white text-gray-700 rounded-xl shadow-sm text-xs font-semibold h-10"
            >
              Home
            </Button>
            <Button 
                variant="outline" 
                onClick={() => router.push('/phase-demo')}
                className="flex-1 bg-white/60 border-white/80 hover:bg-white text-indigo-600 rounded-xl shadow-sm text-xs font-semibold h-10"
            >
              Demo
            </Button>
            <Button 
                onClick={() => router.push('/word-learning-entrance')}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-md shadow-indigo-600/20 text-xs font-semibold h-10"
            >
              Start
            </Button>
          </div>
        </div>

      </div>
    </div>
  );
};

export default LearningStats;
