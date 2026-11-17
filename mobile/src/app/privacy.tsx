// 源文件：pages/privacy.tsx（网页版）。正文占位，正式文案由作者提供后再替换。
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, fontSize, radius, buttonHeight, spacing } from '@/theme';

export default function PrivacyPolicy() {
  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable style={styles.headerBtn} onPress={() => router.replace('/')}>
          <Text style={styles.headerBtnText}>← Home</Text>
        </Pressable>
        <Text style={styles.title}>Privacy Policy</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView style={styles.flex} contentContainerStyle={styles.content}>
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Privacy Policy</Text>
          <Text style={styles.body}>
            This is placeholder content. The full privacy policy text will be provided by the author.
          </Text>
          <Text style={styles.body}>
            Word Learning keeps your learning progress with a guest identity or a signed-in account.
            Learning records are stored on the server and are associated only with your account or this
            device’s guest ID, so you can pick up where you left off.
          </Text>
        </View>
      </ScrollView>
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
  content: { paddingHorizontal: spacing.xl, paddingVertical: spacing.lg },
  card: { backgroundColor: colors.white, borderRadius: radius['3xl'], borderWidth: 1, borderColor: colors.border, padding: spacing.xl, gap: spacing.md },
  sectionTitle: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  body: { fontSize: fontSize.body, color: colors.textStrong, lineHeight: 22 },
});
