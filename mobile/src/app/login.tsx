// 源文件：pages/login.tsx（网页版）。RN 版：凭证写 SecureStore，跳转用 router.replace。
import { router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authenticatedFetch } from '@/lib/authClient';
import { setSecure } from '@/lib/storage';
import { useLearningContext } from '@/context/LearningContext';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

export default function Login() {
  const { setUserId } = useLearningContext();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    if (!username.trim() || !password) {
      setError('Please enter your username and password.');
      return;
    }
    setLoading(true);
    try {
      // 登录不并库（后端 login 不读 X-Guest-Id）；只有注册才把访客记录并入账号
      const response = await authenticatedFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password, remember_me: rememberMe }),
      });
      const result = await response.json();
      if (result.success) {
        await setSecure('session_token', result.data.session_token);
        await setSecure('user_id', result.data.user_id);
        await setSecure('username', result.data.username);
        setUserId(result.data.user_id);
        router.replace('/');
      } else {
        setError(result.error || 'Sign-in failed');
      }
    } catch {
      setError('Network error. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable style={styles.headerBtn} onPress={() => router.replace('/')}>
          <Text style={styles.headerBtnText}>← Home</Text>
        </Pressable>
        <Text style={styles.title}>Sign in</Text>
        <View style={styles.headerSpacer} />
      </View>

      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView style={styles.flex} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.subtitle}>Sign in to continue learning</Text>

          {error && (
            <View style={styles.errorCard}>
              <Text style={styles.errorText}>❌ {error}</Text>
            </View>
          )}

          <View style={styles.card}>
            <Text style={styles.label}>Username or email</Text>
            <TextInput
              style={styles.input}
              value={username}
              onChangeText={setUsername}
              placeholder="Username or email"
              autoCapitalize="none"
              autoCorrect={false}
              placeholderTextColor={colors.textFaint}
            />

            <Text style={styles.label}>Password</Text>
            <View style={styles.passwordRow}>
              <TextInput
                style={[styles.input, styles.passwordInput]}
                value={password}
                onChangeText={setPassword}
                placeholder="Password"
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                autoCorrect={false}
                placeholderTextColor={colors.textFaint}
              />
              <Pressable style={styles.showBtn} onPress={() => setShowPassword(!showPassword)}>
                <Text style={styles.showBtnText}>{showPassword ? 'Hide' : 'Show'}</Text>
              </Pressable>
            </View>

            <Pressable style={styles.rememberRow} onPress={() => setRememberMe(!rememberMe)}>
              <View style={[styles.checkbox, rememberMe && styles.checkboxChecked]}>
                {rememberMe && <Text style={styles.checkboxMark}>✓</Text>}
              </View>
              <Text style={styles.rememberText}>Keep me signed in for 7 days</Text>
            </Pressable>
          </View>

          <Pressable style={[styles.primaryBtn, loading && styles.primaryBtnDisabled]} onPress={handleSubmit} disabled={loading}>
            {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>Sign in</Text>}
          </Pressable>

          <Pressable style={styles.linkBtn} onPress={() => router.replace('/register')}>
            <Text style={styles.linkText}>No account yet? Sign up</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  flex: { flex: 1 },
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
  rememberRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  checkboxChecked: { backgroundColor: colors.primary, borderColor: colors.primary },
  checkboxMark: { fontSize: 14, color: colors.white, fontWeight: '700' },
  rememberText: { fontSize: fontSize.body, color: colors.textMuted },
  primaryBtn: { minHeight: buttonHeight.xl, borderRadius: radius.xl, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  primaryBtnDisabled: { opacity: 0.6 },
  primaryBtnText: { fontSize: fontSize.base, fontWeight: '700', color: colors.white, letterSpacing: 1 },
  linkBtn: { minHeight: buttonHeight.min, alignItems: 'center', justifyContent: 'center' },
  linkText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  deleteSection: { marginTop: spacing.xl, gap: spacing.sm },
  deleteError: { fontSize: fontSize.body, color: colors.dangerText, textAlign: 'center' },
  deleteCard: { backgroundColor: colors.dangerBg, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.dangerBorder, padding: spacing.lg, gap: spacing.sm },
  deleteTitle: { fontSize: fontSize.body, fontWeight: '700', color: colors.dangerText, textAlign: 'center' },
  deleteHint: { fontSize: fontSize.body, color: colors.textMuted, textAlign: 'center' },
  deleteRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  cancelBtn: {
    flex: 1, minHeight: buttonHeight.lg, borderRadius: radius.xl, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  cancelBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.textStrong },
  deleteBtn: { flex: 1, minHeight: buttonHeight.lg, borderRadius: radius.xl, backgroundColor: colors.danger, alignItems: 'center', justifyContent: 'center' },
  deleteBtnText: { fontSize: fontSize.body, fontWeight: '700', color: colors.white },
  deleteLinkText: { fontSize: fontSize.body, fontWeight: '600', color: colors.dangerText },
});
