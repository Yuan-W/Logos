<script setup lang="ts">
import { NConfigProvider, NMessageProvider, darkTheme } from 'naive-ui'
import AppLayout from '@/components/AppLayout.vue'
</script>

<template>
  <NConfigProvider :theme="darkTheme">
    <NMessageProvider>
      <AppLayout />
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
/* App-level overrides if needed */
</style>
