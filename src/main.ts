import { createApp } from 'vue'
import { App } from '@/ui/page/app'
import { router } from '@/config/router/router'
import { setupApiInterceptors } from '@/api/instance'
import { registerAuthGuards } from '@/config/router/guards'
import { useAuthStore } from '@/store/auth-store'
import { Routes } from '@/config/router/routes'
import dayjs from 'dayjs'
import { createPinia } from 'pinia'
import isToday from 'dayjs/plugin/isToday'
import './assets/styles/main.css'

const pinia = createPinia()

setupApiInterceptors(pinia, router)
registerAuthGuards(router, pinia)

const authStore = useAuthStore(pinia)
void authStore.ensureInitialized()

window.addEventListener('auth:logout', () => {
    const currentRoute = router.currentRoute.value
    if (currentRoute.name !== Routes.Login) {
        const redirect = currentRoute.fullPath && currentRoute.fullPath !== '/login'
            ? { redirect: currentRoute.fullPath }
            : undefined
        router.push({
            name: Routes.Login,
            ...(redirect ? { query: redirect } : {}),
        }).catch(() => undefined)
    }
})

const app = createApp(App)

app.config.globalProperties.$dayjs = dayjs
dayjs.extend(isToday)

app
    .use(pinia)
    .use(router)
    .mount('#app')



