<script setup lang="ts">
import type { ChatMessage } from '@/composables/useChat'

defineProps<{
  message: ChatMessage
}>()

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
</script>

<template>
  <div :class="[
    'chat-bubble-enter-active max-w-[80%] p-3 rounded-2xl',
    message.role === 'user'
      ? 'ml-auto bg-logos-primary text-white rounded-br-sm'
      : 'mr-auto bg-logos-surface-alt text-gray-100 rounded-bl-sm'
  ]">
    <!-- Role Label -->
    <div class="text-xs opacity-60 mb-1">
      {{ message.role === 'user' ? '你' : getAgentDisplayName(message.agentName) }}
    </div>

    <!-- Content -->
    <div class="whitespace-pre-wrap break-words">
      {{ message.content }}
    </div>

    <!-- Timestamp -->
    <div class="text-xs opacity-40 mt-1 text-right">
      {{ new Date(message.timestamp).toLocaleTimeString('zh-CN') }}
    </div>
  </div>
</template>
