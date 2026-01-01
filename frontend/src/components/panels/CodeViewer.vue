<script setup lang="ts">
import { NCard, NCode, NScrollbar, NTag } from 'naive-ui'

defineProps<{
    data?: {
        filename?: string
        language?: string
        code?: string
    }
}>()
</script>

<template>
    <div class="space-y-4">
        <NCard size="small" class="glass">
            <template #header>
                <div class="flex justify-between items-center">
                    <span class="font-mono text-sm">{{ data?.filename || 'code.py' }}</span>
                    <NTag v-if="data?.language" size="small" type="info">
                        {{ data.language }}
                    </NTag>
                </div>
            </template>

            <NScrollbar style="max-height: 400px">
                <NCode v-if="data?.code" :code="data.code" :language="data.language || 'python'" :hljs="undefined"
                    class="text-sm" />
                <div v-else class="text-gray-500 italic text-center py-8">
                    暂无代码内容
                </div>
            </NScrollbar>
        </NCard>
    </div>
</template>
