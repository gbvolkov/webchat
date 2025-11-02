import { DefaultAPIInstance } from '@/api/instance'
import type { MessageListResponse, ThreadDetail, ThreadListResponse, ThreadSearchResponse } from './types'

export const ThreadsApi = {
    getThreads(page = 1, limit = 20) {
        return DefaultAPIInstance.get<ThreadListResponse>('/threads', {
            params: { page, limit },
        })
    },

    getThread(threadId: string) {
        return DefaultAPIInstance.get<ThreadDetail>(`/threads/${threadId}`)
    },

    createThread(payload: { title?: string; summary?: string; metadata?: Record<string, unknown> } = {}) {
        return DefaultAPIInstance.post<ThreadDetail>('/threads', payload)
    },

    updateThread(
        threadId: string,
        payload: { title?: string; summary?: string; metadata?: Record<string, unknown>; is_deleted?: boolean } = {},
    ) {
        return DefaultAPIInstance.patch<ThreadDetail>(`/threads/${threadId}`, payload)
    },

    deleteThread(threadId: string) {
        return DefaultAPIInstance.delete<void>(`/threads/${threadId}`)
    },

    getThreadMessages(threadId: string, page = 1, limit = 20) {
        return DefaultAPIInstance.get<MessageListResponse>(`/threads/${threadId}/messages`, {
            params: { page, limit },
        })
    },

    searchThreads(payload: { phrase: string; model_id?: string; limit?: number }) {
        return DefaultAPIInstance.post<ThreadSearchResponse>('/search/threads', payload)
    },
}
