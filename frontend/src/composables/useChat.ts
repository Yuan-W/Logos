import { ref, readonly, watch, computed } from 'vue'
import { useContextStore } from '@/stores/context'
import { useSessionStore } from '@/stores/session'

export interface ChatMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    agentName?: string
    timestamp: number
}

// Prefix for storing chat history per session
const STORAGE_PREFIX = 'logos_chat_'

export function useChat() {
    const messages = ref<ChatMessage[]>([])
    const isStreaming = ref(false)

    const contextStore = useContextStore()
    const sessionStore = useSessionStore()

    // Get current session ID from store
    const currentSessionId = computed(() => sessionStore.currentSessionId)

    /**
     * Load messages for a specific session ID
     */
    const loadMessages = (sessionId: string) => {
        try {
            const stored = localStorage.getItem(`${STORAGE_PREFIX}${sessionId}`)
            if (stored) {
                messages.value = JSON.parse(stored)
            } else {
                messages.value = []
            }
        } catch (e) {
            console.error('Failed to load messages:', e)
            messages.value = []
        }
    }

    /**
     * Save messages for current session
     */
    const saveMessages = () => {
        if (!currentSessionId.value) return
        try {
            localStorage.setItem(
                `${STORAGE_PREFIX}${currentSessionId.value}`,
                JSON.stringify(messages.value)
            )
        } catch (e) {
            console.error('Failed to save messages:', e)
        }
    }

    // Watch for session changes to reload messages
    watch(currentSessionId, (newId) => {
        if (newId) {
            loadMessages(newId)
        } else {
            messages.value = []
        }
    }, { immediate: true })

    // Watch for message changes to auto-save
    watch(messages, saveMessages, { deep: true })

    /**
     * Generate a unique message ID
     */
    const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`

    /**
     * Send a message and stream the response via SSE
     */
    const sendMessage = async (text: string, agentOverride?: string) => {
        if (!currentSessionId.value || isStreaming.value) return

        // Use agent from session, or override if provided
        const session = sessionStore.currentSession
        const currentAgent = agentOverride || session?.agent || 'gm'

        // 1. Add user message immediately
        const userMessage: ChatMessage = {
            id: generateId(),
            role: 'user',
            content: text,
            timestamp: Date.now(),
        }
        messages.value.push(userMessage)

        // Update session title if it's the first message and still default
        if (session && messages.value.length === 1 && session.title === '新对话') {
            sessionStore.updateSession(session.id, {
                title: text.slice(0, 15) + (text.length > 15 ? '...' : '')
            })
        }

        // Update session last modified
        if (session) {
            sessionStore.updateSession(session.id, {
                lastModified: Date.now(),
                agent: currentAgent // Update agent if changed
            })
        }

        // 2. Prepare assistant message placeholder
        const assistantMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: '',
            agentName: currentAgent.toUpperCase(),
            timestamp: Date.now(),
        }
        messages.value.push(assistantMessage)

        // 3. Start SSE connection
        isStreaming.value = true

        const url = new URL('/stream/' + currentSessionId.value, window.location.origin)
        url.searchParams.set('message', text)
        url.searchParams.set('role', currentAgent)
        url.searchParams.set('user_id', 'user_default')

        try {
            const eventSource = new EventSource(url.toString())

            eventSource.addEventListener('message', (event) => {
                try {
                    const data = JSON.parse(event.data)
                    if (data.text_chunk) {
                        const lastMsg = messages.value[messages.value.length - 1]
                        if (lastMsg.role === 'assistant') {
                            lastMsg.content += data.text_chunk
                        }
                    }
                } catch (e) {
                    console.error('Failed to parse message event:', e)
                }
            })

            eventSource.addEventListener('artifact_update', (event) => {
                try {
                    const data = JSON.parse(event.data)
                    contextStore.addArtifact({
                        id: `artifact_${Date.now()}`,
                        type: data.type || 'draft',
                        content: data.content,
                    })

                    if (data.type === 'draft') {
                        contextStore.setPanelData({
                            title: '最新草稿',
                            content: data.content,
                            wordCount: data.content.split(/\s+/).length,
                        })
                    } else if (data.type === 'outline') {
                        contextStore.setPanelData({
                            title: '大纲',
                            content: data.content,
                            wordCount: data.content.split(/\s+/).length,
                        })
                    }
                } catch (e) {
                    console.error('Failed to parse artifact_update event:', e)
                }
            })

            eventSource.addEventListener('tool_start', (event) => {
                try {
                    const data = JSON.parse(event.data)
                    console.log('Tool started:', data.tool_name)
                } catch (e) {
                    console.error('Failed to parse tool_start event:', e)
                }
            })

            eventSource.addEventListener('error', () => {
                eventSource.close()
                isStreaming.value = false
            })

            eventSource.addEventListener('close', () => {
                isStreaming.value = false
            })

            setTimeout(() => {
                if (eventSource.readyState !== EventSource.CLOSED) {
                    eventSource.close()
                    isStreaming.value = false
                }
            }, 120000)

        } catch (error) {
            console.error('Failed to connect to SSE:', error)
            isStreaming.value = false

            const lastMsg = messages.value[messages.value.length - 1]
            if (lastMsg.role === 'assistant' && !lastMsg.content) {
                lastMsg.content = '⚠️ Connection error. Please try again.'
            }
        }
    }

    /**
     * Clear messages for current session
     */
    const clearMessages = () => {
        if (!currentSessionId.value) return
        messages.value = []
        localStorage.removeItem(`${STORAGE_PREFIX}${currentSessionId.value}`)
    }

    return {
        messages: readonly(messages),
        isStreaming: readonly(isStreaming),
        sendMessage,
        clearMessages,
    }
}
