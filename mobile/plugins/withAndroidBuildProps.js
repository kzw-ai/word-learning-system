// 自定义 config plugin：把原生 gradle 设置写进 app.json，避免直接改 prebuild 生成的 android/gradle.properties。
// 设置：
// 1. org.gradle.jvmargs —— Gradle 内存。RN 0.88 的 Kotlin 编译需要更大的 heap/metaspace（默认 512m metaspace 会 OOM）。
// 2. kotlin.compiler.execution.strategy=in-process —— 沙箱环境写不了 ~/Library/Application Support/kotlin，
//    禁用 Kotlin 编译 daemon（daemon 目录写失败时会报错并 fallback，这里直接禁用）。
const { withGradleProperties } = require('expo/config-plugins');

module.exports = function withAndroidBuildProps(config) {
  return withGradleProperties(config, config => {
    const props = config.modResults.filter(
      p => p.key !== 'org.gradle.jvmargs' && p.key !== 'kotlin.compiler.execution.strategy'
    );
    props.push(
      { type: 'property', key: 'org.gradle.jvmargs', value: '-Xmx4096m -XX:MaxMetaspaceSize=2048m' },
      { type: 'property', key: 'kotlin.compiler.execution.strategy', value: 'in-process' }
    );
    config.modResults = props;
    return config;
  });
};
