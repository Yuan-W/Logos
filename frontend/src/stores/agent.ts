import { defineStore } from 'pinia'

export const useAgentStore = defineStore('agent', {
    state: () => ({
        currentAgent: 'gm' as string,
    }),
    actions: {
        setAgent(agent: string) {
            this.currentAgent = agent
        },
    },
})
