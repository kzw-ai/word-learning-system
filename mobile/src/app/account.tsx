// 账号页：登录后从这里退出登录 / 删除账号（Apple 5.1.1(v) 要求 App 内可删账号）。
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authenticatedFetch } from '@/lib/authClient';
import { getSecure } from '@/lib/storage';
import { useLearningContext } from '@/context/LearningContext';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

export default function Account() {
  const { clearAuth } = useLearningContext();
  const [username, setUsername] = useState('');
  const [signingOut, setSigningOut] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    getSecure('username').then(u => setUsername(u ?? ''));
  }, []);

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      // 先让服务端凭证失效（失败不阻塞退出，和网页版 useAuth.logout 一致）
      await authenticatedFetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
    } finally {
      await clearAuth();
      router.replace('/');
    }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      const response = await authenticatedFetch('/api/auth/account/delete', { method: 'POST' });
      const result = await response.json();
      if (response.ok && result.success) {
        // 后端删账号时会一并删 session，这里只需清本地凭证、退回访客身份
        await clearAuth();
        router.replace('/');
      } else {
        setDeleteError(
          response.status === 401
            ? 'Sign in first to delete your account.'
            : (result.error || 'Could not delete the account.')
        );
      }
    } catch {
      setDeleteError('Network error. Please try again later.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable style={styles.headerBtn} onPress={() => router.replace('/')}>
          <Text style={styles.headerBtnText}>← Home</Text>
        </Pressable>
        <Text style={styles.title}>Account</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.label}>Signed in as</Text>
          <Text style={styles.username}>{username || '—'}</Text>
        </View>

        <Pressable style={styles.signoutBtn} onPress={handleSignOut} disabled={signingOut}>
          {signingOut ? <ActivityIndicator color={colors.textStrong} /> : <Text style={styles.signoutText}>Sign out</Text>}
        </Pressable>

        {deleteError && <Text style={styles.deleteError}>{deleteError}</Text>}

        {deleteOpen ? (
          <View style={styles.deleteCard}>
            <Text style={styles.deleteTitle}>Delete your account permanently?</Text>
            <Text style={styles.deleteHint}>This deletes your account and all learning records. This cannot be undone.</Text>
            <View style={styles.deleteRow}>
              <Pressable style={styles.cancelBtn} onPress={() => setDeleteOpen(false)} disabled={deleting}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </Pressable>
              <Pressable style={styles.deleteBtn} onPress={handleDeleteAccount} disabled={deleting}>
                <Text style={styles.deleteBtnText}>{deleting ? 'Deleting…' : 'Delete permanently'}</Text>
              </Pressable>
            </View>
          </View>
        ) : (
          <Pressable style={styles.linkBtn} onPress={() => { setDeleteOpen(true); setDeleteError(null); }}>
            <Text style={styles.deleteLinkText}>Delete my account</Text>
          </Pressable>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgStart },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.xl, paddingVertical: spacing.md },
  headerBtn: {
    minHeight: buttonHeight.min, paddingHorizontal: spacing.md, borderRadius: radius.lg,
    backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center',
  },
  headerBtnText: { fontSize: fontSize.body, fontWeight: '600', color: colors.primaryDark },
  title: { fontSize: fontSize.xl, fontWeight: '800', color: colors.text },
  headerSpacer: { width: 76 },
  content: { paddingHorizontal: spacing.xl, paddingVertical: spacing.lg, gap: spacing.md },
  card: { backgroundColor: colors.white, borderRadius: radius['3xl'], borderWidth: 1, borderColor: colors.border, padding: spacing.xl, gap: spacing.xs },
  label: { fontSize: fontSize.body, color: colors.textMuted },
  username: { fontSize: fontSize.xl, fontWeight: '700', color: colors.text },
  signoutBtn: {
    minHeight: buttonHeight.xl, borderRadius: radius.xl, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  signoutText: { fontSize: fontSize.base, fontWeight: '600', color: colors.textStrong },
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
  linkBtn: { minHeight: buttonHeight.min, alignItems: 'center', justifyContent: 'center' },
  deleteLinkText: { fontSize: fontSize.body, fontWeight: '600', color: colors.dangerText },
});
