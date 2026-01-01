<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import type { ChatMessage } from '@/composables/useChat'

const props = defineProps<{
  message: ChatMessage
}>()

// Configure marked
marked.setOptions({
  breaks: true, // GFM line breaks
  gfm: true,    // GitHub Flavored Markdown
})

// Agent names in Chinese for display
const agentNames: Record<string, string> = {
  gm: '游戏主持',
  GM: '游戏主持',
  narrator: '叙事者',
  NARRATOR: '叙事者',
  writer: '创意写作',
  WRITER: '创意写作',
  coach: '心理教练',
  COACH: '心理教练',
  coder: '编程助手',
  CODER: '编程助手',
}

const getAgentDisplayName = (name?: string) => {
  if (!name) return 'AI'
  return agentNames[name] || name
}

// Render content as Markdown
const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return marked.parse(props.message.content) as string
})
</script>

<template>
  <div :class="[
    'animate-bloom max-w-[95%] p-5 rounded-3xl shadow-sm border transition-all duration-500',
    message.role === 'user'
      ? 'ml-auto bg-brand-primary text-brand-contrast rounded-br-none border-brand-primary shadow-lg shadow-brand-primary/10 font-medium'
      : 'mr-auto bg-app-surface text-app-text border-app-border shadow-sm'
  ]">
    <!-- Role Label -->
    <div class="text-[9px] uppercase tracking-[0.2em] mb-2 font-black opacity-40"
      :class="message.role === 'user' ? 'text-app-bg' : 'text-brand-secondary'">
      {{ message.role === 'user' ? '你' : getAgentDisplayName(message.agentName) }}
    </div>

    <!-- Content (Markdown Rendered) -->
    <div class="prose prose-sm max-w-none break-words leading-relaxed transition-colors duration-500"
      v-html="renderedContent"></div>

    <!-- Timestamp -->
    <div class="text-[9px] opacity-30 mt-3 text-right font-black italic tracking-tighter">
      {{ new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
    </div>
  </div>
</template>
