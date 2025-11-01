import { createApp } from 'vue'
import { App } from '@/ui/page/app'
import { router } from '@/config/router/router'
import dayjs from 'dayjs'
import { createPinia } from 'pinia'
import isToday from 'dayjs/plugin/isToday'
import './assets/styles/main.css'

const pinia = createPinia()

const app = createApp(App)

app.config.globalProperties.$dayjs = dayjs
dayjs.extend(isToday)

app
    .use(pinia)
    .use(router)
    .mount('#app')

