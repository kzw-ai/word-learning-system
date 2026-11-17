// 源文件：pages/register.tsx（网页版）。RN 版：跳转用 router.replace。
import { router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authenticatedFetch } from '@/lib/authClient';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

const LANGUAGES = ['English', 'Español', 'Français', 'Deutsch', '日本語', '한국어'];

export default function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [nativeLanguage, setNativeLanguage] = useState('English');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    setError(null);
    // 客户端验证
    if (password !== confirmPassword) {
      setError('The passwords don’t match');
      return;
    }
    if (password.length < 6) {
      setError('Use at least 6 characters for the password');
      return;
    }
    if (!username.trim()) {
      setError('Please enter a username');
      return;
    }
    setLoading(true);
    try {
      // 还没登录：请求头只有 X-Guest-Id，后端据此把访客期间的学习记录并入新账号
      const response = await authenticatedFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username: username.trim(),
          password,
          email: email.trim() || null,
          native_language: nativeLanguage,
        }),
      });
      const result = await response.json();
      if (result.success) {
        setSuccess(true);
      } else {
        setError(result.error || 'Sign-up failed');
      }
    } catch {
      setError('Network error. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <SafeAreaView style={styles.center}>
        <View style={styles.successCard}>
          <Text style={styles.successEmoji}>🎉</Text>
          <Text style={styles.successTitle}>You’re signed up!</Text>
          <Text style={styles.successText}>Your account is ready. Sign in to continue.</Text>
          <Pressable style={styles.primaryBtn} onPress={() => router.replace('/login')}>
            <Text style={styles.primaryBtnText}>Sign in now</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable style={styles.headerBtn} onPress={() => router.replace('/')}>
          <Text style={styles.headerBtnText}>← Home</Text>
        </Pressable>
        <Text style={styles.title}>Sign up</Text>
        <View style={styles.headerSpacer} />
      </View>

      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView style={styles.flex} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.subtitle}>Create an account to keep your progress on any device</Text>

          {error && (
            <View style={styles.errorCard}>
              <Text style={styles.errorText}>❌ {error}</Text>
            </View>
          )}

          <View style={styles.card}>
            <Text style={styles.label}>Username *</Text>
            <TextInput
              style={styles.input}
              value={username}
              onChangeText={setUsername}
              placeholder="Username"
              autoCapitalize="none"
              autoCorrect={false}
              placeholderTextColor={colors.textFaint}
            />

            <Text style={styles.label}>Email (optional)</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="Email"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              placeholderTextColor={colors.textFaint}
            />

            <Text style={styles.label}>Password *</Text>
            <View style={styles.passwordRow}>
              <TextInput
                style={[styles.input, styles.passwordInput]}
                value={password}
                onChangeText={setPassword}
                placeholder="At least 6 characters"
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                autoCorrect={false}
                placeholderTextColor={colors.textFaint}
              />
              <Pressable style={styles.showBtn} onPress={() => setShowPassword(!showPassword)}>
                <Text style={styles.showBtnText}>{showPassword ? 'Hide' : 'Show'}</Text>
              </Pressable>
            </View>

            <Text style={styles.label}>Confirm password *</Text>
            <TextInput
              style={styles.input}
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="Type the password again"
              secureTextEntry={!showPassword}
              autoCapitalize="none"
              autoCorrect={false}
              placeholderTextColor={colors.textFaint}
            />

            <Text style={styles.label}>Native language</Text>
            <View style={styles.langWrap}>
              {LANGUAGES.map(lang => (
                <Pressable
                  key={lang}
                  style={[styles.langChip, nativeLanguage === lang && styles.langChipActive]}
                  onPress={() => setNativeLanguage(lang)}
                >
                  <Text style={[styles.langText, nativeLanguage === lang && styles.langTextActive]}>{lang}</Text>
                </Pressable>
              ))}
            </View>
          </View>

          <Pressable style={[styles.primaryBtn, loading && styles.primaryBtnDisabled]} onPress={handleSubmit} disabled={loading}>
            {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>Sign up</Text>}
          </Pressable>

          <Pressable style={styles.linkBtn} onPress={() => router.replace('/login')}>
            <Text style={styles.linkText}>Already have an account? Sign in</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  flex: { flex: 1 },
  center: { flex: 1, backgroundColor: colors.bgStart, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.xl },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.xl, paddingVertical: spacing.md },
  headerBtn: {
    minHeight: buttonHeight.min, paddingHorizontal: spacing.md, borderRadius: radius.lg,
    backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center',
  },
  headerBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  title: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  headerSpacer: { width: 76 },
  content: { paddingHorizontal: spacing.xl, paddingVertical: spacing.lg, gap: spacing.md },
  subtitle: { fontSize: fontSize.base, color: colors.textMuted, marginBottom: spacing.sm },
  errorCard: { backgroundColor: colors.dangerBg, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.dangerBorder, padding: spacing.lg },
  errorText: { fontSize: fontSize.body, color: colors.dangerText },
  card: { backgroundColor: colors.white, borderRadius: radius['3xl'], borderWidth: 1, borderColor: colors.border, padding: spacing.xl, gap: spacing.sm },
  label: { fontSize: fontSize.body, fontWeight: '600', color: colors.textStrong },
  input: {
    minHeight: buttonHeight.lg, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.bgEnd, paddingHorizontal: spacing.md, fontSize: fontSize.body, color: colors.text,
  },
  passwordRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  passwordInput: { flex: 1 },
  showBtn: { minHeight: buttonHeight.lg, paddingHorizontal: spacing.md, alignItems: 'center', justifyContent: 'center' },
  showBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  langWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  langChip: {
    minHeight: buttonHeight.min, paddingHorizontal: spacing.md, borderRadius: radius.lg,
    backgroundColor: colors.bgEnd, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center',
  },
  langChipActive: { backgroundColor: colors.primaryBg, borderColor: colors.primary },
  langText: { fontSize: fontSize.body, color: colors.textMuted },
  langTextActive: { color: colors.primaryDark, fontWeight: '600' },
  primaryBtn: { minHeight: buttonHeight.xl, borderRadius: radius.xl, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  primaryBtnDisabled: { opacity: 0.6 },
  primaryBtnText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
  linkBtn: { minHeight: buttonHeight.min, alignItems: 'center', justifyContent: 'center' },
  linkText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  successCard: {
    width: '100%', backgroundColor: colors.white, borderRadius: radius['3xl'], borderWidth: 1, borderColor: colors.primaryBorder,
    padding: spacing.xl, alignItems: 'center', gap: spacing.md,
  },
  successEmoji: { fontSize: 48 },
  successTitle: { fontSize: fontSize['2xl'], fontWeight: '800', color: colors.text },
  successText: { fontSize: fontSize.body, color: colors.textMuted, textAlign: 'center', marginBottom: spacing.sm },
});
