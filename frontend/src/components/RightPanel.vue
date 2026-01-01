<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { NTabs, NTabPane, NEmpty } from 'naive-ui'
import { useAgentStore } from '@/stores/agent'
import { useContextStore } from '@/stores/context'

import CharacterSheet from './panels/CharacterSheet.vue'
import NovelDraft from './panels/NovelDraft.vue'
import CodeViewer from './panels/CodeViewer.vue'

const agentStore = useAgentStore()
const contextStore = useContextStore()

// Dynamic panel mapping based on agent type
const panelComponents = {
  gm: markRaw(CharacterSheet),
  narrator: markRaw(CharacterSheet),
  writer: markRaw(NovelDraft),
  screenwriter: markRaw(NovelDraft),
  coder: markRaw(CodeViewer),
  researcher: markRaw(CodeViewer),
  coach: null,
}

const activePanel = computed(() => {
  return panelComponents[agentStore.currentAgent as keyof typeof panelComponents] || null
})

const panelTitle = computed(() => {
  const titles: Record<string, string> = {
    gm: '角色卡',
    narrator: '角色卡',
    writer: '草稿预览',
    screenwriter: '剧本预览',
    coder: '代码查看器',
    researcher: '研究笔记',
  }
  return titles[agentStore.currentAgent] || '上下文'
})
</script>

<template>
  <div class="h-full flex flex-col bg-logos-surface/80">
    <!-- Header -->
    <div class="p-4 border-b border-gray-700/50">
      <h3 class="text-sm font-semibold text-gray-300">
        {{ panelTitle }}
      </h3>
    </div>

    <!-- Dynamic Panel Content -->
    <div class="flex-1 overflow-auto p-4">
      <component v-if="activePanel" :is="activePanel" :data="contextStore.panelData" />
      <NEmpty v-else description="该智能体没有上下文面板" class="h-full flex items-center justify-center" />
    </div>

    <!-- Artifacts Tab (if any) -->
    <div v-if="contextStore.artifacts.length" class="border-t border-gray-700/50">
      <NTabs type="line" size="small" class="px-2">
        <NTabPane v-for="artifact in contextStore.artifacts" :key="artifact.id" :name="artifact.id"
          :tab="artifact.type === 'draft' ? '草稿' : artifact.type">
          <div class="p-2 text-sm text-gray-400 max-h-32 overflow-auto">
            {{ artifact.content }}
          </div>
        </NTabPane>
      </NTabs>
    </div>
  </div>
</template>
