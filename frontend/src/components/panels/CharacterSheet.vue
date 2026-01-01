<script setup lang="ts">
import { NCard, NDescriptions, NDescriptionsItem, NProgress, NTag } from 'naive-ui'

defineProps<{
  data?: {
    name?: string
    hp?: number
    maxHp?: number
    ac?: number
    conditions?: string[]
    stats?: Record<string, number>
  }
}>()

// Translate common conditions to Chinese
const conditionNames: Record<string, string> = {
  'Grappled': '擒抱',
  'Poisoned': '中毒',
  'Stunned': '震慑',
  'Prone': '倒地',
  'Frightened': '恐惧',
  'Blinded': '目盲',
  'Charmed': '魅惑',
  'Deafened': '耳聋',
  'Exhaustion': '力竭',
  'Incapacitated': '失能',
  'Invisible': '隐形',
  'Paralyzed': '麻痹',
  'Petrified': '石化',
  'Restrained': '束缚',
  'Unconscious': '昏迷',
}

const translateCondition = (cond: string) => conditionNames[cond] || cond
</script>

<template>
  <div class="space-y-4">
    <NCard size="small" class="glass">
      <template #header>
        <span class="text-lg font-bold">{{ data?.name || '暂无角色' }}</span>
      </template>

      <!-- HP Bar -->
      <div v-if="data?.hp !== undefined" class="mb-4">
        <div class="flex justify-between text-sm mb-1">
          <span>生命值</span>
          <span>{{ data.hp }} / {{ data.maxHp }}</span>
        </div>
        <NProgress type="line" :percentage="((data.hp || 0) / (data.maxHp || 1)) * 100"
          :color="(data.hp || 0) / (data.maxHp || 1) > 0.5 ? '#22c55e' : '#ef4444'"
          :rail-color="'rgba(255,255,255,0.1)'" />
      </div>

      <!-- Stats -->
      <NDescriptions v-if="data?.stats" :column="3" size="small">
        <NDescriptionsItem v-for="(value, stat) in data.stats" :key="stat" :label="stat">
          {{ value }}
        </NDescriptionsItem>
      </NDescriptions>

      <!-- Conditions -->
      <div v-if="data?.conditions?.length" class="mt-4">
        <div class="text-xs text-gray-500 mb-2">状态效果</div>
        <div class="flex flex-wrap gap-1">
          <NTag v-for="cond in data.conditions" :key="cond" size="small" type="warning">
            {{ translateCondition(cond) }}
          </NTag>
        </div>
      </div>
    </NCard>

    <!-- Placeholder if no data -->
    <div v-if="!data" class="text-center text-gray-500 py-8">
      <p>开始游戏后将显示角色信息</p>
    </div>
  </div>
</template>
