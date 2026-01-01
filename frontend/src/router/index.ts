import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '@/views/ChatView.vue'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/',
            name: 'home',
            component: ChatView,
        },
        {
            path: '/chat/:agent?',
            name: 'chat',
            component: ChatView,
        },
    ],
})

export default router
