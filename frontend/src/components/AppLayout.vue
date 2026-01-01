<script setup lang="ts">
import { ref, computed } from 'vue'
import { NLayout, NLayoutSider, NLayoutContent } from 'naive-ui'
import LeftSidebar from './LeftSidebar.vue'
import ChatBox from './ChatBox.vue'
import RightPanel from './RightPanel.vue'
import { useAgentStore } from '@/stores/agent'

const agentStore = useAgentStore()
const rightPanelCollapsed = ref(false)

const toggleRightPanel = () => {
  rightPanelCollapsed.value = !rightPanelCollapsed.value
}
</script>

<template>
  <NLayout has-sider class="h-screen">
    <!-- Left Sidebar: Navigation -->
    <NLayoutSider
      bordered
      :width="250"
      :collapsed-width="64"
      collapse-mode="width"
      show-trigger
      class="glass"
    >
      <LeftSidebar />
    </NLayoutSider>

    <!-- Main Content Area -->
    <NLayout>
      <NLayoutContent class="flex h-full">
        <!-- Chat Area -->
        <div class="flex-1 flex flex-col min-w-0">
          <ChatBox />
        </div>

        <!-- Right Panel: Context (Collapsible) -->
        <div
          :class="[
            'transition-all duration-300 border-l border-gray-700/50',
            rightPanelCollapsed ? 'w-0 overflow-hidden' : 'w-[400px]'
          ]"
        >
          <RightPanel v-if="!rightPanelCollapsed" />
        </div>
      </NLayoutContent>
    </NLayout>

    <!-- Toggle Button for Right Panel -->
    <button
      @click="toggleRightPanel"
      class="fixed right-4 top-4 z-50 p-2 rounded-lg glass hover:bg-logos-primary/20 transition-colors"
    >
      <span v-if="rightPanelCollapsed">◀</span>
      <span v-else>▶</span>
    </button>
  </NLayout>
</template>

<style scoped>
.n-layout-sider {
  background: rgba(17, 24, 39, 0.8) !important;
}
</style>
