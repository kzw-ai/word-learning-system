import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, LogIn } from 'lucide-react';
import { buildApiUrl } from "@/src/lib/apiClient";
import { useLearningContext } from '@/src/context/LearningContext';

const Login = () => {
  const router = useRouter();
  const { setUserId } = useLearningContext();
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    remember_me: false
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch(buildApiUrl('/api/auth/login'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',  // 允许cookie
        body: JSON.stringify(formData)
      });

      const result = await response.json();

      if (result.success) {
        // 保存session token到localStorage
        localStorage.setItem('session_token', result.data.session_token);
        localStorage.setItem('user_id', result.data.user_id);
        localStorage.setItem('username', result.data.username);
        // 学习系统随即改用账号身份；此前只存了 user_id，学习页仍用旧身份，
        // 请求里的用户与登录凭证对不上而被拒绝
        setUserId(result.data.user_id);

        // 跳转到首页
        router.push('/');
      } else {
        setError(result.error || '登录失败');
      }
    } catch (err) {
      setError('网络错误，请检查后端服务是否启动');
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    'w-full px-4 py-3 text-sm bg-white/70 border border-white/60 rounded-xl ' +
    'placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 ' +
    'focus:border-transparent transition-all';

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-[calc(env(safe-area-inset-bottom)+1rem)] px-5 flex flex-col relative z-20 overflow-y-auto">
          {/* Header */}
          <div className="mt-6 mb-8">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-200 mb-4">
              <LogIn size={26} className="text-white" strokeWidth={2.2} />
            </div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight">
              用户登录
            </h1>
            <p className="text-sm text-gray-500 mt-1 font-medium">登录您的账户开始学习</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="glass-panel rounded-2xl p-4 border-red-200 bg-red-50/80">
                <p className="text-sm text-red-600">❌ {error}</p>
              </div>
            )}

            <div className="glass-panel rounded-2xl p-5 space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="username" className="text-sm font-medium text-gray-700">
                  用户名或邮箱
                </Label>
                <input
                  id="username"
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className={inputClass}
                  placeholder="输入用户名或邮箱"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-sm font-medium text-gray-700">
                  密码
                </Label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className={`${inputClass} pr-11`}
                    placeholder="输入密码"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div className="flex items-center pt-1">
                <input
                  id="remember"
                  type="checkbox"
                  checked={formData.remember_me}
                  onChange={(e) => setFormData({ ...formData, remember_me: e.target.checked })}
                  className="mr-2.5 w-4 h-4 accent-indigo-600"
                />
                <Label htmlFor="remember" className="text-sm text-gray-600 cursor-pointer">
                  记住我（7天内免登录）
                </Label>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-2xl border-none text-white font-bold tracking-wide text-sm bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg hover:shadow-indigo-200 disabled:from-gray-300 disabled:to-gray-300 disabled:shadow-none transition-all duration-300"
            >
              {loading ? '登录中...' : '登录'}
            </Button>

            <div className="text-center">
              <button
                type="button"
                onClick={() => router.push('/register')}
                className="text-sm text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
              >
                还没有账户？立即注册
              </button>
            </div>

            <div className="glass-card rounded-2xl p-4 bg-indigo-50/60">
              <p className="text-sm text-indigo-900 mb-1 font-semibold">💡 测试账号提示</p>
              <p className="text-sm text-indigo-700">
                所有现有测试用户默认密码：
                <code className="bg-indigo-100 px-1.5 py-0.5 rounded-md ml-1">password123</code>
              </p>
            </div>
          </form>

          {/* Bottom Action */}
          <div className="mt-auto pt-6">
            <Button
              variant="ghost"
              onClick={() => router.push('/')}
              className="w-full h-11 rounded-2xl text-gray-600 bg-white/50 hover:bg-white/80 border border-white/60 transition-all"
            >
              返回首页
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
