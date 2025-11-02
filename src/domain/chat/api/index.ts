import { DefaultAPIInstance } from '@/api/instance'
import { ISendMessageRequest, IModelsResponse, IAttachmentUpload } from '@/domain/chat/api/types'
import { useAuthStore } from '@/store/auth-store'

export const ChatApi = {
    async sendMessage(threadId: string, message: string, modelId: string, modelLabel?: string, attachments?: IAttachmentUpload[]) {
        const authStore = useAuthStore()
        await authStore.ensureInitialized()
        const senderId = authStore.userId
        if (!senderId) {
            throw new Error('Unable to determine the current user. Please sign in again.')
        }

        const url = `/threads/${threadId}/messages`
        const data: ISendMessageRequest = {
            sender_id: senderId,
            sender_type: 'user',
            text: message,
            model: modelId,
            model_label: modelLabel,
            attachments,
        }

        return DefaultAPIInstance.post(url, data)
    },

    getModels() {
        return DefaultAPIInstance.get<IModelsResponse>('/models')
    },
}
