<script setup lang="ts">
import { ref } from 'vue'
import { NLayout, NLayoutSider, NLayoutContent } from 'naive-ui'
import LeftSidebar from './LeftSidebar.vue'
import ChatBox from './ChatBox.vue'
import RightPanel from './RightPanel.vue'

const rightPanelCollapsed = ref(false)

const toggleRightPanel = () => {
  rightPanelCollapsed.value = !rightPanelCollapsed.value
}
</script>

<template>
  <NLayout has-sider class="h-screen bg-app-bg transition-colors duration-500">
    <!-- Left Sidebar: Navigation -->
    <NLayoutSider bordered :width="260" collapse-mode="width" class="!bg-app-surface transition-colors duration-500">
      <LeftSidebar />
    </NLayoutSider>

    <!-- Main Content Area -->
    <NLayout class="h-full bg-transparent" content-style="display: flex; flex-direction: column; height: 100%;">
      <NLayoutContent class="h-full bg-transparent" content-style="display: flex; height: 100%;">
        <!-- Chat Area -->
        <main class="flex-1 flex flex-col min-w-0 h-full bg-transparent">
          <ChatBox />
        </main>

        <!-- Right Panel: Context (Collapsible) -->
        <aside :class="[
          'transition-all duration-500 border-l border-app-border overflow-hidden bg-app-surface h-full',
          rightPanelCollapsed ? 'w-0' : 'w-96'
        ]">
          <RightPanel />
        </aside>
      </NLayoutContent>
    </NLayout>

    <!-- Toggle Button for Right Panel -->
    <button @click="toggleRightPanel"
      class="fixed right-6 top-4 z-50 p-2 rounded-xl glass hover:scale-110 active:scale-95 transition-all duration-300 shadow-lg">
      <span v-if="rightPanelCollapsed" class="text-xs">◀</span>
      <span v-else class="text-xs">▶</span>
    </button>
  </NLayout>
</template>

<style scoped>
/* Removed hardcoded background that caused sidebar to be dark in light mode */
</style>
