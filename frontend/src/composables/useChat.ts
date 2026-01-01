import { ref, readonly } from 'vue'
import { useContextStore } from '@/stores/context'

export interface ChatMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    agentName?: string
    timestamp: number
}

export function useChat() {
    const messages = ref<ChatMessage[]>([])
    const isStreaming = ref(false)
    const currentSessionId = ref(`session_${Date.now()}`)

    const contextStore = useContextStore()

    /**
     * Generate a unique message ID
     */
    const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`

    /**
     * Send a message and stream the response via SSE
     */
    const sendMessage = async (text: string, agent: string = 'gm') => {
        // 1. Add user message immediately
        const userMessage: ChatMessage = {
            id: generateId(),
            role: 'user',
            content: text,
            timestamp: Date.now(),
        }
        messages.value.push(userMessage)

        // 2. Prepare assistant message placeholder
        const assistantMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: '',
            agentName: agent.toUpperCase(),
            timestamp: Date.now(),
        }
        messages.value.push(assistantMessage)

        // 3. Start SSE connection
        isStreaming.value = true

        const url = new URL('/stream/' + currentSessionId.value, window.location.origin)
        url.searchParams.set('message', text)
        url.searchParams.set('role', agent)
        url.searchParams.set('user_id', 'user_default')

        try {
            const eventSource = new EventSource(url.toString())

            eventSource.addEventListener('message', (event) => {
                try {
                    const data = JSON.parse(event.data)
                    if (data.text_chunk) {
                        // Append text to the last assistant message
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
                    // Update context store with artifact
                    contextStore.addArtifact({
                        id: `artifact_${Date.now()}`,
                        type: data.type || 'draft',
                        content: data.content,
                    })

                    // If it's a draft, also update panel data
                    if (data.type === 'draft') {
                        contextStore.setPanelData({
                            title: 'Latest Draft',
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
                    // Optionally show tool execution in UI
                    console.log('Tool started:', data.tool_name)
                } catch (e) {
                    console.error('Failed to parse tool_start event:', e)
                }
            })

            eventSource.addEventListener('error', () => {
                console.error('SSE connection error')
                eventSource.close()
                isStreaming.value = false
            })

            // Handle stream end (SSE doesn't have a built-in 'end' event, 
            // we rely on server closing the connection)
            eventSource.addEventListener('close', () => {
                isStreaming.value = false
            })

            // Timeout fallback (if server doesn't close connection gracefully)
            setTimeout(() => {
                if (eventSource.readyState !== EventSource.CLOSED) {
                    eventSource.close()
                    isStreaming.value = false
                }
            }, 120000) // 2 minute timeout

        } catch (error) {
            console.error('Failed to connect to SSE:', error)
            isStreaming.value = false

            // Add error message
            const lastMsg = messages.value[messages.value.length - 1]
            if (lastMsg.role === 'assistant' && !lastMsg.content) {
                lastMsg.content = '⚠️ Connection error. Please try again.'
            }
        }
    }

    /**
     * Clear all messages
     */
    const clearMessages = () => {
        messages.value = []
        currentSessionId.value = `session_${Date.now()}`
    }

    /**
     * Start a new session
     */
    const newSession = () => {
        clearMessages()
        contextStore.clearArtifacts()
    }

    return {
        messages: readonly(messages),
        isStreaming: readonly(isStreaming),
        currentSessionId: readonly(currentSessionId),
        sendMessage,
        clearMessages,
        newSession,
    }
}
