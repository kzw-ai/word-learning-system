import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, UserPlus } from 'lucide-react';
import { buildApiUrl } from "@/src/lib/apiClient";

const Register = () => {
  const router = useRouter();
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    email: '',
    native_language: 'English'
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 客户端验证
    if (formData.password !== formData.confirmPassword) {
      setError('The passwords don’t match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Use at least 6 characters for the password');
      return;
    }

    if (!formData.username.trim()) {
      setError('Please enter a username');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(buildApiUrl('/api/auth/register'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          password: formData.password,
          email: formData.email || null,
          native_language: formData.native_language
        })
      });

      const result = await response.json();

      if (result.success) {
        setSuccess(true);
        // 3秒后自动跳转到登录页
        setTimeout(() => {
          router.push('/login');
        }, 3000);
      } else {
        setError(result.error || 'Sign-up failed');
      }
    } catch (err) {
      setError('Network error. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    'w-full px-4 py-3 text-sm bg-white/70 border border-white/60 rounded-xl ' +
    'placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 ' +
    'focus:border-transparent transition-all';

  if (success) {
    return (
      <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
        <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
          <div className="h-full flex flex-col items-center justify-center px-8">
            <div className="glass-panel rounded-3xl p-8 text-center w-full">
              <div className="text-6xl mb-4">🎉</div>
              <h2 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600 mb-2">
                You’re signed up!
              </h2>
              <p className="text-sm text-gray-600 mb-1">Your account is ready</p>
              <p className="text-sm text-gray-400 mb-6">Taking you to sign in…</p>
              <Button
                onClick={() => router.push('/login')}
                className="w-full h-12 rounded-2xl border-none text-white font-bold tracking-wide text-sm bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg hover:shadow-indigo-200 transition-all duration-300"
              >
                Sign in now
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-[100dvh] bg-gray-50">
      <div className="w-full max-w-[430px] h-[100dvh] overflow-hidden modern-gradient-bg relative">
        <div className="h-full pt-[calc(env(safe-area-inset-top)+1rem)] pb-[calc(env(safe-area-inset-bottom)+1rem)] px-5 flex flex-col relative z-20 overflow-y-auto">
          {/* Header */}
          <div className="mt-6 mb-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-200 mb-4">
              <UserPlus size={26} className="text-white" strokeWidth={2.2} />
            </div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight">
              Sign up
            </h1>
            <p className="text-sm text-slate-600 mt-1 font-medium">Create an account to keep your progress on any device</p>
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
                  Username <span className="text-rose-600" aria-hidden="true">*</span>
                </Label>
                <input
                  id="username"
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className={inputClass}
                  placeholder="Username"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-sm font-medium text-gray-700">
                  Email (optional)
                </Label>
                <input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className={inputClass}
                  placeholder="Email"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-sm font-medium text-gray-700">
                  Password <span className="text-rose-600" aria-hidden="true">*</span>
                </Label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className={`${inputClass} pr-11`}
                    placeholder="At least 6 characters"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-1 top-1/2 -translate-y-1/2 p-2.5 text-slate-500 hover:text-slate-700 transition-colors"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword" className="text-sm font-medium text-gray-700">
                  Confirm password <span className="text-rose-600" aria-hidden="true">*</span>
                </Label>
                <input
                  id="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.confirmPassword}
                  onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                  className={inputClass}
                  placeholder="Type the password again"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="native_language" className="text-sm font-medium text-gray-700">
                  Native language
                </Label>
                <select
                  id="native_language"
                  value={formData.native_language}
                  onChange={(e) => setFormData({ ...formData, native_language: e.target.value })}
                  className={`${inputClass} appearance-none`}
                >
                  <option value="English">English</option>
                  <option value="Spanish">Español</option>
                  <option value="French">Français</option>
                  <option value="German">Deutsch</option>
                  <option value="Japanese">日本語</option>
                  <option value="Korean">한국어</option>
                </select>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-2xl border-none text-white font-bold tracking-wide text-sm bg-gradient-to-r from-indigo-500 to-purple-600 hover:shadow-lg hover:shadow-indigo-200 disabled:from-gray-300 disabled:to-gray-300 disabled:shadow-none transition-all duration-300"
            >
              {loading ? 'Signing up…' : 'Sign up'}
            </Button>

            <div className="text-center">
              <button
                type="button"
                onClick={() => router.push('/login')}
                className="inline-block py-2 text-sm text-indigo-700 hover:text-indigo-800 font-semibold transition-colors"
              >
                Already have an account? Sign in
              </button>
            </div>
          </form>

          {/* Bottom Action */}
          <div className="mt-auto pt-6">
            <Button
              variant="ghost"
              onClick={() => router.push('/')}
              className="w-full h-11 rounded-2xl text-gray-600 bg-white/50 hover:bg-white/80 border border-white/60 transition-all"
            >
              Back to home
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;
