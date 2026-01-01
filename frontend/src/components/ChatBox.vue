<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { h } from 'vue'
import { NButton, NModal, NPopselect, NIcon } from 'naive-ui'
import {
  PaperPlaneOutline as SendIcon,
  TrashOutline as TrashIcon,
  SparklesOutline as SparklesIcon,
  ChevronDown as ChevronDownIcon
} from '@vicons/ionicons5'
import { useChat } from '@/composables/useChat'
import { useSessionStore } from '@/stores/session'
import ChatBubble from './ChatBubble.vue'

const sessionStore = useSessionStore()
const inputMessage = ref('')
const chatContainer = ref<HTMLElement | null>(null)
const showClearModal = ref(false)

const { messages, isStreaming, sendMessage, clearMessages } = useChat()

// Agent options - using icons for better quality
const agentOptions = [
  { label: '🎲 游戏主持 (GM)', value: 'gm' },
  { label: '✍️ 创意写作 (Writer)', value: 'writer' },
  { label: '🌿 心理教练 (Coach)', value: 'coach' },
  { label: '💻 编程助手 (Coder)', value: 'coder' }
]

const renderAgentLabel = (option: { label: string; value: string }) => {
  const parts = option.label.split(' ')
  return h('div', { class: 'flex items-center justify-between w-full gap-4 py-2' }, [
    h('div', { class: 'flex items-center gap-3' }, [
      h('span', { class: 'text-lg leading-none' }, parts[0]), // Icon
      h('span', { class: 'font-bold text-app-text text-sm' }, parts[1]) // Name
    ]),
    h('span', { class: 'text-[11px] uppercase tracking-wider opacity-40 font-bold' }, parts[2] || 'AGENT') // Role
  ])
}

const currentSession = computed(() => sessionStore.currentSession)

const handleAgentChange = (value: string) => {
  if (currentSession.value) {
    sessionStore.updateSession(currentSession.value.id, { agent: value })
  }
}

const currentAgentInfo = computed(() => {
  if (!currentSession.value?.agent) return { icon: '', name: '' }
  const option = agentOptions.find(opt => opt.value === currentSession.value?.agent)
  if (!option) return { icon: '', name: '' }

  const parts = option.label.split(' ')
  return {
    icon: parts[0],
    name: parts.slice(1).join(' ')
  }
})

const handleSend = async () => {
  const text = inputMessage.value.trim()
  if (!text || isStreaming.value) return

  inputMessage.value = ''
  await sendMessage(text)
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const handleClearChat = () => {
  clearMessages()
  showClearModal.value = false
}

// Auto-scroll to bottom
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
  <div class="chat-wrapper">
    <!-- Header -->
    <header class="chat-header glass">
      <div class="header-left">
        <div class="status-icon">
          <NIcon :size="20">
            <SparklesIcon />
          </NIcon>
        </div>

        <div class="session-info">
          <h2 class="session-title">
            <span v-if="!currentSession" class="idle-text">待命</span>
            <span v-else>{{ currentSession.title }}</span>
          </h2>
          <div v-if="currentSession" class="agent-selector-container">
            <NPopselect v-model:value="currentSession.agent" :options="agentOptions" trigger="click"
              @update:value="handleAgentChange" :render-label="renderAgentLabel" scrollable>
              <div class="agent-trigger">
                <span class="agent-badge">AGENT</span>
                <div class="agent-divider"></div>
                <div class="agent-identity">
                  <span class="agent-icon">
                    {{ currentAgentInfo.icon }}
                  </span>
                  <span class="agent-name">
                    {{ currentAgentInfo.name }}
                  </span>
                </div>
                <NIcon :size="10" class="chevron">
                  <ChevronDownIcon />
                </NIcon>
              </div>
            </NPopselect>
          </div>
        </div>
      </div>

      <div class="header-right">
        <NButton quaternary circle @click="showClearModal = true" v-if="currentSession" class="clear-btn">
          <template #icon>
            <NIcon>
              <TrashIcon />
            </NIcon>
          </template>
        </NButton>
      </div>
    </header>

    <!-- Clear Chat Modal -->
    <NModal v-model:show="showClearModal" preset="card" class="custom-modal logout-modal" :auto-focus="false">
      <div class="modal-content">
        <div class="modal-icon-wrapper">
          <TrashIcon class="modal-icon" />
        </div>
        <h3 class="modal-title">清空记忆？</h3>
        <p class="modal-description">
          此操作将永久删除本次会话的所有记忆，<br>如同将字迹从沙滩上抹去。
        </p>
        <div class="modal-actions">
          <NButton class="btn-cancel" secondary @click="showClearModal = false">
            保留
          </NButton>
          <NButton class="btn-confirm" type="primary" @click="handleClearChat">
            确认清空
          </NButton>
        </div>
      </div>
    </NModal>

    <!-- Chat Messages -->
    <main class="chat-main">
      <div ref="chatContainer" class="messages-viewport">
        <div class="messages-list">
          <template v-if="messages.length > 0">
            <ChatBubble v-for="msg in messages" :key="msg.timestamp" :message="msg" />
          </template>

          <!-- Empty State -->
          <div v-else class="empty-state animate-bloom">
            <div class="empty-icon-wrapper">
              <SparklesIcon class="empty-icon" />
            </div>
            <div class="empty-text">
              <h2 class="empty-title">静候晨曦，开始对话</h2>
              <p class="empty-subtitle">与万物对话，书写您的传奇</p>
            </div>
          </div>

          <!-- Streaming Indicator -->
          <div v-if="isStreaming" class="streaming-indicator">
            <div class="loading-dots">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>
            <span class="streaming-text">THINKING...</span>
          </div>
        </div>
      </div>
    </main>

    <!-- Chat Input Area -->
    <footer class="chat-footer">
      <div class="input-container">
        <div class="input-inner">
          <textarea v-model="inputMessage" placeholder="与万物对话..." class="chat-textarea" @keydown="handleKeydown"
            rows="1" ref="textareaRef"></textarea>

          <NButton circle size="large" type="primary" class="send-btn" @click="handleSend"
            :disabled="!inputMessage.trim() || isStreaming">
            <template #icon>
              <NIcon :size="24">
                <SendIcon />
              </NIcon>
            </template>
          </NButton>
        </div>

        <div class="input-hints">
          <span class="hint-text">SHIFT + ENTER 换行 · ENTER 发送</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.chat-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--bg-color);
  transition: background-color 0.5s ease;
  overflow: hidden;
}

/* Header Styles */
.chat-header {
  height: auto;
  min-height: 4.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  z-index: 10;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.status-icon {
  padding: 0.5rem;
  color: var(--brand-color);
  transition: transform 0.3s ease;
}

.status-icon:hover {
  transform: rotate(12deg);
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  /* Space between title and selector */
  padding-top: 0.25rem;
}

.session-title {
  font-size: 0.875rem;
  font-weight: 900;
  letter-spacing: 0.025em;
  color: var(--text-color);
  margin: 0;
}

.idle-text {
  opacity: 0.4;
}

/* Agent Selector Wrapper */
.agent-trigger {
  background-color: rgba(133, 109, 86, 0.05);
  /* Using direct RGB as Fallback */
  background-color: color-mix(in srgb, var(--brand-color), transparent 95%);
  border: 1px solid transparent;
  border-radius: 9999px;
  padding: 0.375rem 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.agent-trigger:hover {
  background-color: color-mix(in srgb, var(--brand-color), transparent 90%);
  border-color: color-mix(in srgb, var(--brand-color), transparent 90%);
  box-shadow: 0 1px 2px var(--shadow-color);
}

.agent-badge {
  font-size: 0.625rem;
  text-transform: uppercase;
  font-weight: 900;
  letter-spacing: 0.1em;
  color: var(--brand-color);
  opacity: 0.6;
}

.agent-divider {
  height: 0.75rem;
  width: 1px;
  background-color: color-mix(in srgb, var(--brand-color), transparent 90%);
}

.agent-identity {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 7.5rem;
}

.agent-icon {
  font-size: 1rem;
}

.agent-name {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-color);
  opacity: 0.9;
}

.chevron {
  opacity: 0.3;
  transition: opacity 0.3s ease;
}

.agent-trigger:hover .chevron {
  opacity: 1;
}

/* Main Content Area */
.chat-main {
  flex: 1;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.messages-viewport {
  width: 100%;
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.messages-list {
  width: 100%;
  max-width: 56rem;
  /* 4xl */
  padding: 2.5rem 1rem 12rem;
  /* Bottom padding for floating footer */
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
}

/* Empty State */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 2rem;
  min-height: 50vh;
}

.empty-icon-wrapper {
  width: 6rem;
  height: 6rem;
  border-radius: 9999px;
  background-color: color-mix(in srgb, var(--brand-color), transparent 95%);
  border: 1px solid color-mix(in srgb, var(--brand-color), transparent 90%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.02);
}

.empty-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--brand-color);
  opacity: 0.6;
}

.empty-title {
  font-size: 1.875rem;
  font-weight: 900;
  color: var(--text-color);
  letter-spacing: -0.025em;
  opacity: 0.8;
  margin: 0;
}

.empty-subtitle {
  font-size: 1rem;
  color: var(--text-color);
  opacity: 0.4;
  margin: 1rem 0 0;
  font-weight: 500;
  letter-spacing: 0.025em;
}

/* Streaming Loader */
.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  margin-left: 1rem;
  background-color: color-mix(in srgb, var(--surface-color), transparent 50%);
  backdrop-filter: blur(8px);
  border: 1px solid color-mix(in srgb, var(--brand-color), transparent 90%);
  border-radius: 1.5rem;
  width: fit-content;
  color: var(--brand-color);
}

.loading-dots {
  display: flex;
  gap: 0.375rem;
}

.dot {
  width: 0.375rem;
  height: 0.375rem;
  background-color: currentColor;
  border-radius: 9999px;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) {
  animation-delay: -0.32s;
}

.dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {

  0%,
  80%,
  100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1);
  }
}

.streaming-text {
  font-size: 0.7rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  opacity: 0.5;
  margin-left: 0.75rem;
}

/* Footer & Input Area */
.chat-footer {
  position: relative;
  z-index: 10;
  width: 100%;
  pointer-events: none;
}

.input-container {
  width: 100%;
  max-width: 56rem;
  /* 4xl */
  margin: 0 auto;
  padding: 4rem 1.5rem 3rem;
  background: linear-gradient(to top, var(--bg-color) 40%, transparent 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: auto;
}

.input-inner {
  width: 100%;
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 2rem;
  box-shadow: 0 10px 40px var(--shadow-color);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.input-inner:focus-within {
  border-color: color-mix(in srgb, var(--brand-color), transparent 70%);
  box-shadow: 0 15px 50px color-mix(in srgb, var(--brand-color), transparent 85%);
}

.chat-textarea {
  flex: 1;
  background-color: transparent;
  border: none;
  color: var(--text-color);
  font-size: 1.125rem;
  font-weight: 500;
  line-height: 1.6;
  padding: 0.75rem 1rem;
  resize: none;
  min-height: 3rem;
  max-height: 15rem;
  outline: none;
}

.chat-textarea::placeholder {
  color: var(--text-color);
  opacity: 0.2;
}

.send-btn {
  flex-shrink: 0;
  width: 3.5rem !important;
  height: 3.5rem !important;
  background-color: var(--brand-color) !important;
  border: none !important;
  box-shadow: 0 8px 20px color-mix(in srgb, var(--brand-color), transparent 70%) !important;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}

.send-btn:not(:disabled):hover {
  transform: scale(1.05);
  box-shadow: 0 12px 28px color-mix(in srgb, var(--brand-color), transparent 60%) !important;
}

.input-hints {
  margin-top: 1rem;
  opacity: 0.2;
}

.hint-text {
  font-size: 0.65rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.3em;
}

/* Modal Styling */
.modal-content {
  padding: 2.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.modal-icon-wrapper {
  width: 4rem;
  height: 4rem;
  border-radius: 1.25rem;
  background-color: color-mix(in srgb, var(--brand-color), transparent 90%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.modal-icon {
  width: 2rem;
  height: 2rem;
  color: var(--brand-color);
}

.modal-title {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--text-color);
  margin-bottom: 0.75rem;
}

.modal-description {
  font-size: 0.95rem;
  color: var(--text-color);
  opacity: 0.6;
  text-align: center;
  margin-bottom: 2.5rem;
  line-height: 1.6;
}

.modal-actions {
  display: flex;
  gap: 1rem;
  width: 100%;
}

.btn-cancel,
.btn-confirm {
  flex: 1;
  border-radius: 1rem !important;
  height: 3.5rem !important;
  font-weight: 700 !important;
}

.btn-confirm {
  background-color: var(--brand-color) !important;
  color: var(--text-on-brand) !important;
  border: none !important;
}

/* Naive UI Overrides */
:deep(.n-select .n-base-selection) {
  --n-border-radius: 0.75rem !important;
  background-color: transparent !important;
}

.custom-modal {
  width: 440px;
  max-width: 90vw;
  border-radius: 2rem !important;
}
</style>
