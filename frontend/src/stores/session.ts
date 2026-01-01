import { defineStore } from 'pinia'

export interface Session {
    id: string
    title: string
    agent: string
    lastModified: number
}

const STORAGE_KEY = 'logos_sessions'

export const useSessionStore = defineStore('session', {
    state: () => ({
        sessions: [] as Session[],
        currentSessionId: null as string | null,
    }),

    getters: {
        currentSession: (state) => state.sessions.find(s => s.id === state.currentSessionId) || null,
        sortedSessions: (state) => [...state.sessions].sort((a, b) => b.lastModified - a.lastModified)
    },

    actions: {
        init() {
            const stored = localStorage.getItem(STORAGE_KEY)
            if (stored) {
                try {
                    this.sessions = JSON.parse(stored)
                } catch (e) {
                    console.error('Failed to parse sessions', e)
                }
            }

            // If no sessions, create one
            if (this.sessions.length === 0) {
                this.createNewSession()
            } else if (!this.currentSessionId) {
                // Select most recent
                this.currentSessionId = this.sortedSessions[0].id
            }
        },

        createNewSession(agent: string = 'gm') {
            const newSession: Session = {
                id: `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
                title: '新对话',
                agent: agent,
                lastModified: Date.now()
            }
            this.sessions.unshift(newSession)
            this.currentSessionId = newSession.id
            this.saveToStorage()
            return newSession.id
        },

        switchSession(id: string) {
            if (this.sessions.find(s => s.id === id)) {
                this.currentSessionId = id
            }
        },

        updateSession(id: string, updates: Partial<Session>) {
            const session = this.sessions.find(s => s.id === id)
            if (session) {
                Object.assign(session, updates, { lastModified: Date.now() })
                this.saveToStorage()
            }
        },

        deleteSession(id: string) {
            const index = this.sessions.findIndex(s => s.id === id)
            if (index !== -1) {
                this.sessions.splice(index, 1)

                // Remove associated messages
                localStorage.removeItem(`logos_chat_${id}`)

                // If deleted active session, switch to another or create new
                if (this.currentSessionId === id) {
                    if (this.sessions.length > 0) {
                        this.currentSessionId = this.sessions[0].id
                    } else {
                        this.createNewSession()
                    }
                }
                this.saveToStorage()
            }
        },

        saveToStorage() {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this.sessions))
        }
    }
})
