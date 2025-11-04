import { createApp } from 'vue'
import dayjs from 'dayjs'
import isToday from 'dayjs/plugin/isToday'
import { createPinia } from 'pinia'
import { App } from '@/ui/page/app'
import { router } from '@/config/router/router'
import { setupApiInterceptors } from '@/api/instance'
import { registerAuthGuards } from '@/config/router/guards'
import { useAuthStore } from '@/store/auth-store'
import { useLocaleStore } from '@/store/locale-store'
import { Routes } from '@/config/router/routes'
import { i18n } from '@/config/i18n'
import './assets/styles/main.css'

const pinia = createPinia()

setupApiInterceptors(pinia, router)
registerAuthGuards(router, pinia)

useLocaleStore(pinia)
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
    .use(i18n)
    .use(router)
    .mount('#app')



