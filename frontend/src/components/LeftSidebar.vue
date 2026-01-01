<script setup lang="ts">
import { NMenu, NIcon, NDivider, NAvatar } from 'naive-ui'
import {
  GameController as GameIcon,
  Create as WriteIcon,
  Heart as CoachIcon,
  Code as CodeIcon
} from '@vicons/ionicons5'
import { useAgentStore } from '@/stores/agent'
import { h, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const agentStore = useAgentStore()

const renderIcon = (icon: any) => () => h(NIcon, null, { default: () => h(icon) })

const menuOptions = computed(() => [
  {
    label: '🎲 游戏主持',
    key: 'gm',
    icon: renderIcon(GameIcon),
  },
  {
    label: '✍️ 创意写作',
    key: 'writer',
    icon: renderIcon(WriteIcon),
  },
  {
    label: '💚 心理教练',
    key: 'coach',
    icon: renderIcon(CoachIcon),
  },
  {
    label: '💻 编程助手',
    key: 'coder',
    icon: renderIcon(CodeIcon),
  },
])

const handleSelect = (key: string) => {
  agentStore.setAgent(key)
  router.push(`/chat/${key}`)
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Logo Header -->
    <div class="p-4 flex items-center gap-3">
      <NAvatar round size="medium" src="https://api.dicebear.com/7.x/bottts/svg?seed=logos" />
      <div>
        <h1 class="text-lg font-bold gradient-text">Logos AI</h1>
        <p class="text-xs text-gray-500">个人 AI 操作系统</p>
      </div>
    </div>

    <NDivider class="!my-2" />

    <!-- Navigation Menu -->
    <NMenu :options="menuOptions" :value="agentStore.currentAgent" @update:value="handleSelect" class="flex-1" />

    <!-- Footer -->
    <div class="p-4 text-xs text-gray-500 text-center">
      v0.1.0 | 多智能体系统
    </div>
  </div>
</template>

<style scoped>
:deep(.n-menu) {
  background: transparent !important;
}
</style>
