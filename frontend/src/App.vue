<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { NConfigProvider, NMessageProvider, darkTheme, lightTheme } from 'naive-ui'
import AppLayout from '@/components/AppLayout.vue'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

onMounted(() => {
  themeStore.initTheme()
})

const currentTheme = computed(() => themeStore.isDark ? darkTheme : lightTheme)
</script>

<template>
  <NConfigProvider :theme="currentTheme">
    <NMessageProvider>
      <AppLayout />
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
/* App-level overrides if needed */
</style>
