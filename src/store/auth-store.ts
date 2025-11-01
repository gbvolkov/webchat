import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
    const userName = ref('Гость')
    const userId = ref<string>('1')

    return {
        userName,
        userId,
    }
})
