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
    <NCard size="small" class="glass">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="font-bold">{{ data?.title || '草稿' }}</span>
          <span v-if="data?.wordCount" class="text-xs text-gray-500">
            {{ data.wordCount }} 字
          </span>
        </div>
      </template>

      <NScrollbar style="max-height: 400px">
        <div class="prose prose-invert prose-sm max-w-none">
          <div v-if="data?.content" class="whitespace-pre-wrap text-gray-300">
            {{ data.content }}
          </div>
          <div v-else class="text-gray-500 italic">
            暂无草稿内容，开始创作吧！
          </div>
        </div>
      </NScrollbar>
    </NCard>
  </div>
</template>
