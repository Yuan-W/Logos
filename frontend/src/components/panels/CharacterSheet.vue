<script setup lang="ts">
import { NCard, NProgress, NTag } from 'naive-ui'

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
    <NCard size="small" class="glass !rounded-soul border-none shadow-sm overflow-hidden">
      <template #header>
        <span class="text-xl font-black text-brand-secondary italic">{{ data?.name || '静候召唤的角色' }}</span>
      </template>

      <!-- HP Bar -->
      <div v-if="data?.hp !== undefined"
        class="mb-6 p-5 bg-app-bg/60 rounded-3xl border border-app-border/40 shadow-inner">
        <div class="flex justify-between text-[10px] font-black uppercase tracking-[0.2em] opacity-40 mb-3">
          <span>生命力 (HP)</span>
          <span class="text-brand-primary">{{ data.hp }} / {{ data.maxHp }}</span>
        </div>
        <NProgress type="line" :percentage="Number(((data.hp || 0) / (data.maxHp || 1)) * 100)"
          :color="(data.hp || 0) / (data.maxHp || 1) > 0.5 ? 'var(--brand-color)' : 'var(--accent-green)'"
          :rail-color="'rgba(0,0,0,0.05)'" :show-indicator="false" :height="10" class="!rounded-full shadow-sm" />
      </div>

      <!-- Stats Grid -->
      <div v-if="data?.stats" class="grid grid-cols-3 gap-4 mb-6">
        <div v-for="(value, stat) in data.stats" :key="stat"
          class="flex flex-col items-center p-4 bg-app-bg border border-app-border/30 rounded-soul shadow-sm hover:-translate-y-1 transition-all duration-500">
          <span class="text-[9px] uppercase font-black tracking-widest opacity-30">{{ stat }}</span>
          <span class="text-xl font-black text-brand-primary">{{ value }}</span>
        </div>
      </div>

      <!-- Conditions -->
      <div v-if="data?.conditions?.length" class="mt-4 p-4 border-t border-app-border/30">
        <div class="text-[10px] font-black uppercase tracking-widest opacity-40 mb-3">当前状态</div>
        <div class="flex flex-wrap gap-2">
          <NTag v-for="cond in data.conditions" :key="cond" size="small" :bordered="false"
            class="!bg-brand-primary/10 !text-brand-primary !font-bold !rounded-full">
            {{ translateCondition(cond) }}
          </NTag>
        </div>
      </div>
    </NCard>

    <!-- Placeholder if no data -->
    <div v-if="!data" class="flex flex-col items-center justify-center py-16 opacity-30 text-center animate-pulse">
      <div class="w-12 h-12 rounded-full border-2 border-dashed border-current mb-4"></div>
      <p class="text-sm font-bold">角色数据尚在远方...</p>
    </div>
  </div>
</template>
