import { createRouter, createWebHistory } from 'vue-router'
import { Routes } from './routes'
import { GwpChatPage } from '@/ui/page/gwp-chat-page'
import { ChatsHistory } from '@/ui/page/chats-history'
import { ChatsLibrary } from '@/ui/page/chats-library'
import { GwpChatPageId } from '@/ui/page/gwp-chat-page-id'
import { GwpChatSearchPage } from '@/ui/page/gwp-chat-search'
import { LoginPage } from '@/ui/page/auth/login'

export const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            redirect: `/${Routes.Chat}`
        },

        {
            path: '/login',
            name: Routes.Login,
            component: LoginPage,
            meta: {
                requiresAuth: false,
                layout: 'blank',
            },
        },

        {
            path: `/${Routes.Chat}`,
            name: Routes.Chat,
            component: GwpChatPage,
            meta: {
                requiresAuth: true,
            },
        },

        {
            path: `/${Routes.Chat}/:id`,
            name: `${Routes.ChatDetail}`,
            component: GwpChatPageId,
            props: true,
            meta: {
                requiresAuth: true,
            },
        },

        {
            path: `/${Routes.ChatsHistory}`,
            name: Routes.ChatsHistory,
            component: ChatsHistory,
            meta: {
                requiresAuth: true,
            },
        },

        {
            path: `/${Routes.ChatsLibrary}`,
            name: Routes.ChatsLibrary,
            component: ChatsLibrary,
            meta: {
                requiresAuth: true,
            },
        },

        {
            path: `/${Routes.ChatSearch}`,
            name: Routes.ChatSearch,
            component: GwpChatSearchPage,
            meta: {
                requiresAuth: true,
            },
        },
    ],
})

