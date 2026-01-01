import { defineStore } from 'pinia'

export interface Artifact {
    id: string
    type: string
    content: string
}

export const useContextStore = defineStore('context', {
    state: () => ({
        panelData: null as Record<string, any> | null,
        artifacts: [] as Artifact[],
    }),
    actions: {
        setPanelData(data: Record<string, any>) {
            this.panelData = data
        },
        addArtifact(artifact: Artifact) {
            // Keep only latest 10 artifacts
            this.artifacts.unshift(artifact)
            if (this.artifacts.length > 10) {
                this.artifacts.pop()
            }
        },
        clearArtifacts() {
            this.artifacts = []
            this.panelData = null
        },
    },
})
