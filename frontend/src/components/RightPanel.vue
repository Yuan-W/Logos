<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { NTabs, NTabPane, NEmpty } from 'naive-ui'
import { useSessionStore } from '@/stores/session'
import { useContextStore } from '@/stores/context'

import CharacterSheet from './panels/CharacterSheet.vue'
import NovelDraft from './panels/NovelDraft.vue'
import CodeViewer from './panels/CodeViewer.vue'

const sessionStore = useSessionStore()
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

const currentAgent = computed(() => sessionStore.currentSession?.agent || 'gm')

const activePanel = computed(() => {
  return panelComponents[currentAgent.value as keyof typeof panelComponents] || null
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
  return titles[currentAgent.value] || '上下文'
})
</script>

<template>
  <div
    class="h-full flex flex-col bg-app-surface border-l border-app-border transition-all duration-500 overflow-hidden">
    <!-- Header -->
    <header class="h-16 flex items-center px-6 border-b border-app-border glass shrink-0">
      <h3 class="text-sm font-black uppercase tracking-widest text-brand-secondary">
        {{ panelTitle }}
      </h3>
    </header>

    <!-- Dynamic Panel Content -->
    <main class="flex-1 overflow-auto p-6 animate-bloom">
      <component v-if="activePanel" :is="activePanel" :data="(contextStore.panelData as any)" />
      <div v-else class="h-full flex flex-col items-center justify-center opacity-30 text-center">
        <NEmpty description="本智能体暂无交互面板" />
      </div>
    </main>

    <!-- Artifacts Tab (if any) -->
    <section v-if="contextStore.artifacts.length" class="border-t border-app-border bg-app-bg/50 shrink-0">
      <NTabs type="line" size="small" class="px-4">
        <NTabPane v-for="artifact in contextStore.artifacts" :key="artifact.id" :name="artifact.id"
          :tab="artifact.type === 'draft' ? '📜 文稿' : '📦 ' + artifact.type">
          <div class="p-4 text-xs font-medium leading-relaxed opacity-70 max-h-48 overflow-auto">
            {{ artifact.content }}
          </div>
        </NTabPane>
      </NTabs>
    </section>
  </div>
</template>
