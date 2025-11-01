import { DefaultAPIInstance } from '@/api/instance'
import { ISendMessageRequest, IModelsResponse, IAttachmentUpload } from '@/domain/chat/api/types'
import { useAuthStore } from '@/store/auth-store'

export const ChatApi = {
    sendMessage(threadId: string, message: string, modelId: string, modelLabel?: string, attachments?: IAttachmentUpload[]) {
        const authStore = useAuthStore()
        const url = `/threads/${threadId}/messages`
        const data: ISendMessageRequest = {
            sender_id: authStore.userId,
            sender_type: 'user',
            text: message,
            model: modelId,
            model_label: modelLabel,
            attachments,
        }

        return DefaultAPIInstance.post(url, data, {
            headers: {
                'X-User-Id': authStore.userId,
            },
        })
    },

    getModels() {
        const authStore = useAuthStore()

        return DefaultAPIInstance.get<IModelsResponse>('/models', {
            headers: {
                'X-User-Id': authStore.userId,
            },
        })
    },
}
