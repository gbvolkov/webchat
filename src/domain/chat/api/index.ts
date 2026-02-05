import { API_BASE_URL, DefaultAPIInstance } from '@/api/instance'
import { ISendMessageRequest, IModelsResponse, IAttachmentUpload } from '@/domain/chat/api/types'
import { useAuthStore } from '@/store/auth-store'

export const ChatApi = {
    async sendMessage(
        threadId: string,
        message: string,
        modelId: string,
        modelLabel?: string,
        attachments?: IAttachmentUpload[],
        options: { signal?: AbortSignal } = {},
    ) {
        const authStore = useAuthStore()
        await authStore.ensureInitialized()
        const senderId = authStore.userId
        if (!senderId) {
            throw new Error('Unable to determine the current user. Please sign in again.')
        }

        const url = `${API_BASE_URL}/threads/${threadId}/messages/stream`
        const data: ISendMessageRequest = {
            sender_id: senderId,
            sender_type: 'user',
            text: message,
            model: modelId,
            model_label: modelLabel,
            attachments,
        }

        return authStore.authorizedFetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'text/event-stream',
            },
            body: JSON.stringify(data),
            signal: options.signal,
        })
    },

    getModels() {
        return DefaultAPIInstance.get<IModelsResponse>('/models')
    },
}
