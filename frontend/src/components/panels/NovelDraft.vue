<script setup lang="ts">
import { NCard, NScrollbar } from 'naive-ui'

defineProps<{
  data?: {
    title?: string
    content?: string
    wordCount?: number
  }
}>()
</script>

<template>
  <div class="space-y-4">
    <NCard size="small" class="glass !rounded-2xl border-none shadow-sm">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="font-black text-brand-secondary tracking-tight">{{ data?.title || '正在进行的创作' }}</span>
          <span v-if="data?.wordCount" class="text-[10px] font-bold opacity-40 px-2 py-0.5 bg-app-bg rounded-full">
            {{ data.wordCount }} 字
          </span>
        </div>
      </template>

      <NScrollbar style="max-height: 500px">
        <div class="prose prose-sm max-w-none">
          <div v-if="data?.content" class="whitespace-pre-wrap leading-loose">
            {{ data.content }}
          </div>
          <div v-else class="text-app-text/30 italic py-10 text-center">
            暂无文稿内容，开始您的灵感之旅吧！
          </div>
        </div>
      </NScrollbar>
    </NCard>
  </div>
</template>
