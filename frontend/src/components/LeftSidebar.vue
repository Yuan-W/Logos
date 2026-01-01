<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { NButton, NDivider, NScrollbar, NPopconfirm, NIcon, NTooltip } from 'naive-ui'
import {
  Add as AddIcon,
  ChatbubbleEllipsesOutline as ChatIcon,
  TrashOutline as TrashIcon,
  SunnyOutline as SunIcon,
  MoonOutline as MoonIcon
} from '@vicons/ionicons5'
import { useSessionStore } from '@/stores/session'
import { useThemeStore } from '@/stores/theme'

const sessionStore = useSessionStore()
const themeStore = useThemeStore()

onMounted(() => {
  sessionStore.init()
})

const sessions = computed(() => sessionStore.sortedSessions)
const currentSessionId = computed(() => sessionStore.currentSessionId)

const handleNewChat = () => {
  sessionStore.createNewSession()
}

const handleSelectSession = (id: string) => {
  sessionStore.switchSession(id)
}

const handleDeleteSession = (id: string, e: Event) => {
  e.stopPropagation()
  sessionStore.deleteSession(id)
}

const formatTime = (timestamp: number) => {
  const date = new Date(timestamp)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}
</script>

<template>
  <div class="h-full flex flex-col w-64 border-r border-app-border bg-app-surface transition-all duration-500">
    <!-- Logo Header - Modern Organic Style -->
    <div class="p-6 flex items-center gap-4">
      <div
        class="w-12 h-12 rounded-2xl bg-brand-primary flex items-center justify-center shadow-lg shadow-brand-primary/20 border border-white/20 transition-all duration-700">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"
          class="w-7 h-7 text-brand-contrast transition-colors duration-500">
          <path d="M12 3L4 19H20L12 3Z" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
          <path d="M12 8V15" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
          <circle cx="12" cy="18" r="1.5" fill="currentColor" />
        </svg>
      </div>
      <div>
        <h1 class="text-xl font-black tracking-tighter text-app-text transition-colors duration-500">Logos AI</h1>
        <p class="text-[9px] uppercase font-black tracking-[0.2em] text-app-text opacity-40">
          {{ themeStore.isDark ? 'Bonfire Night' : 'Sunlit Wood' }}
        </p>
      </div>
    </div>

    <!-- New Chat Button - Organic Style -->
    <div class="px-4 py-2">
      <NButton block type="primary" size="large" @click="handleNewChat"
        class="!rounded-2xl !bg-brand-primary !border-none shadow-lg shadow-brand-primary/30 hover:scale-[1.02] transition-all duration-500 !text-brand-contrast">
        <template #icon>
          <NIcon>
            <AddIcon />
          </NIcon>
        </template>
        开启新会话
      </NButton>
    </div>

    <div class="p-4">
      <p class="text-[10px] font-black text-app-text uppercase tracking-[0.3em] mb-2 opacity-30">会话记忆</p>
      <NDivider class="!m-0 !opacity-10 !border-app-text" />
    </div>

    <!-- Session List -->
    <div class="flex-1 overflow-hidden px-2">
      <NScrollbar>
        <div class="space-y-1.5 py-2">
          <div v-for="session in sessions" :key="session.id" @click="handleSelectSession(session.id)"
            class="group relative flex items-center gap-3 p-4 rounded-soul cursor-pointer transition-all duration-500 animate-bloom overflow-hidden"
            :class="[
              session.id === currentSessionId
                ? 'bg-brand-primary/10 text-brand-primary font-bold shadow-sm ring-1 ring-brand-primary/20'
                : 'hover:bg-brand-primary/5 text-app-text opacity-70 hover:opacity-100 border border-transparent'
            ]">
            <div v-if="session.id === currentSessionId" class="absolute left-0 top-0 w-1 h-full bg-brand-primary"></div>

            <NIcon :size="18" :class="session.id === currentSessionId ? 'text-brand-primary' : 'opacity-40'">
              <ChatIcon />
            </NIcon>

            <div class="flex-1 min-w-0">
              <div class="text-[13px] truncate">
                {{ session.title }}
              </div>
              <div class="flex justify-between items-center mt-1">
                <span class="text-[8px] uppercase font-black tracking-widest opacity-40">{{ session.agent }}</span>
                <span class="text-[10px] opacity-30 font-medium">{{ formatTime(session.lastModified) }}</span>
              </div>
            </div>

            <div class="opacity-0 group-hover:opacity-100 transition-opacity" v-if="sessions.length > 1">
              <NPopconfirm @positive-click="(e) => handleDeleteSession(session.id, e)">
                <template #trigger>
                  <div class="p-1 hover:text-red-500 transition-colors" @click.stop>
                    <NIcon :size="16">
                      <TrashIcon />
                    </NIcon>
                  </div>
                </template>
                移除
              </NPopconfirm>
            </div>
          </div>
        </div>
      </NScrollbar>
    </div>

    <!-- Footer with Theme Toggle -->
    <div class="p-4 border-t border-app-border flex items-center justify-between">
      <div class="text-[10px] text-app-text font-bold opacity-30 tracking-widest uppercase">LOGOS v0.3.0</div>

      <NTooltip trigger="hover">
        <template #trigger>
          <button @click="themeStore.toggleTheme"
            class="p-2.5 rounded-xl bg-app-surface border border-app-border hover:scale-110 transition-all duration-300 shadow-sm">
            <NIcon :size="18" :class="themeStore.isDark ? 'text-brand-primary' : 'text-brand-secondary'">
              <SunIcon v-if="themeStore.isDark" />
              <MoonIcon v-else />
            </NIcon>
          </button>
        </template>
        时光流转
      </NTooltip>
    </div>
  </div>
</template>

<style scoped>
.rounded-soul {
  border-radius: 1.5rem;
}
</style>
