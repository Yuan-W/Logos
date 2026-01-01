<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { NInput, NButton, NScrollbar, NSpin } from 'naive-ui'
import { useChat } from '@/composables/useChat'
import { useAgentStore } from '@/stores/agent'
import ChatBubble from './ChatBubble.vue'

const agentStore = useAgentStore()
const inputMessage = ref('')
const chatContainer = ref<HTMLElement | null>(null)

const { messages, isStreaming, sendMessage } = useChat()

// Agent display names in Chinese
const agentNames: Record<string, string> = {
  gm: '游戏主持',
  narrator: '叙事者',
  writer: '创意写作',
  screenwriter: '编剧',
  coach: '心理教练',
  psychologist: '心理咨询',
  coder: '编程助手',
  researcher: '深度研究',
}

const currentAgentName = computed(() => agentNames[agentStore.currentAgent] || agentStore.currentAgent)

const handleSend = async () => {
  const text = inputMessage.value.trim()
  if (!text) return

  inputMessage.value = ''
  await sendMessage(text, agentStore.currentAgent)
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// Auto-scroll to bottom when new messages arrive
watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  }
)
</script>

<template>
  <div class="flex flex-col h-full bg-logos-surface/50">
    <!-- Header -->
    <div class="p-4 border-b border-gray-700/50 glass">
      <h2 class="text-lg font-semibold">
        正在与
        <span class="gradient-text">{{ currentAgentName }}</span>
        对话
      </h2>
    </div>

    <!-- Messages Area -->
    <NScrollbar ref="chatContainer" class="flex-1 p-4">
      <div class="space-y-4">
        <ChatBubble v-for="(msg, index) in messages" :key="index" :message="msg" />

        <!-- Streaming Indicator -->
        <div v-if="isStreaming" class="flex items-center gap-2 text-gray-400">
          <NSpin size="small" />
          <span class="text-sm">AI 正在思考...</span>
        </div>
      </div>
    </NScrollbar>

    <!-- Input Area -->
    <div class="p-4 border-t border-gray-700/50 glass">
      <div class="flex gap-2">
        <NInput v-model:value="inputMessage" type="textarea" placeholder="输入消息..."
          :autosize="{ minRows: 1, maxRows: 4 }" @keydown="handleKeydown" class="flex-1" />
        <NButton type="primary" :loading="isStreaming" :disabled="!inputMessage.trim()" @click="handleSend">
          发送
        </NButton>
      </div>
    </div>
  </div>
</template>
