import { createRouter, createWebHistory } from 'vue-router'
import { Routes } from './routes'
import { GwpChatPage } from '@/ui/page/gwp-chat-page'
import { ChatsHistory } from '@/ui/page/chats-history'
import { ChatsLibrary } from '@/ui/page/chats-library'
import { GwpChatPageId } from '@/ui/page/gwp-chat-page-id'
import { GwpChatSearchPage } from '@/ui/page/gwp-chat-search'

export const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            redirect: `/${Routes.Chat}`
        },

        {
            path: `/${Routes.Chat}`,
            name: Routes.Chat,
            component: GwpChatPage,
        },

        {
            path: `/${Routes.Chat}/:id`,
            name: `${Routes.ChatDetail}`,
            component: GwpChatPageId,
            props: true
        },

        {
            path: `/${Routes.ChatsHistory}`,
            name: Routes.ChatsHistory,
            component: ChatsHistory,
        },

        {
            path: `/${Routes.ChatsLibrary}`,
            name: Routes.ChatsLibrary,
            component: ChatsLibrary,
        },

        {
            path: `/${Routes.ChatSearch}`,
            name: Routes.ChatSearch,
            component: GwpChatSearchPage,
        },
    ],
})
