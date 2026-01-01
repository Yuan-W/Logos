import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
    const isDark = ref(localStorage.getItem('logos_theme') !== 'light')

    const toggleTheme = () => {
        isDark.value = !isDark.value
        localStorage.setItem('logos_theme', isDark.value ? 'dark' : 'light')

        // Update class on html element for tailwind
        if (isDark.value) {
            document.documentElement.classList.add('dark')
        } else {
            document.documentElement.classList.remove('dark')
        }
    }

    // Initial setup
    const initTheme = () => {
        if (isDark.value) {
            document.documentElement.classList.add('dark')
        } else {
            document.documentElement.classList.remove('dark')
        }
    }

    return { isDark, toggleTheme, initTheme }
})
