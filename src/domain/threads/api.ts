import { DefaultAPIInstance } from '@/api/instance'
import { useAuthStore } from '@/store/auth-store'
import type { MessageListResponse, ThreadDetail, ThreadListResponse, ThreadSearchResponse } from './types'

const withUserHeader = () => {
    const authStore = useAuthStore()

    return {
        headers: {
            'X-User-Id': authStore.userId,
        },
    }
}

export const ThreadsApi = {
    getThreads(page = 1, limit = 20) {
        return DefaultAPIInstance.get<ThreadListResponse>('/threads', {
            params: { page, limit },
            ...withUserHeader(),
        })
    },

    getThread(threadId: string) {
        return DefaultAPIInstance.get<ThreadDetail>(`/threads/${threadId}`, withUserHeader())
    },

    createThread(payload: { title?: string; summary?: string; metadata?: Record<string, unknown> } = {}) {
        return DefaultAPIInstance.post<ThreadDetail>('/threads', payload, withUserHeader())
    },

    updateThread(
        threadId: string,
        payload: { title?: string; summary?: string; metadata?: Record<string, unknown>; is_deleted?: boolean } = {},
    ) {
        return DefaultAPIInstance.patch<ThreadDetail>(`/threads/${threadId}`, payload, withUserHeader())
    },

    deleteThread(threadId: string) {
        return DefaultAPIInstance.delete<void>(`/threads/${threadId}`, withUserHeader())
    },

    getThreadMessages(threadId: string, page = 1, limit = 20) {
        return DefaultAPIInstance.get<MessageListResponse>(`/threads/${threadId}/messages`, {
            params: { page, limit },
            ...withUserHeader(),
        })
    },

    searchThreads(payload: { phrase: string; model_id?: string; limit?: number }) {
        return DefaultAPIInstance.post<ThreadSearchResponse>('/search/threads', payload, withUserHeader())
    },
}
