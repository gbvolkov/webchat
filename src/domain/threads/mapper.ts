import type { MessageDTO, MessageAttachmentDTO, SenderType } from '@/domain/threads/types'
import { Role, TMessageContent } from '@/ui/widget/chat/types'

const ROLE_MAPPER: Record<SenderType, Role> = {
    user: Role.User,
    assistant: Role.Ai,
    system: Role.Ai,
} as const

const mapAttachmentsToFiles = (attachments?: MessageAttachmentDTO[]) => {
    if (!attachments?.length) return []
    return attachments.map((attachment) => ({
        name: attachment.filename,
        type: attachment.content_type,
        src: attachment.data_base64 ? `data:${attachment.content_type};base64,${attachment.data_base64}` : undefined,
    }))
}

export const mapThreadInfoToMessageContent = (threadInfo: MessageDTO[]): TMessageContent[] => {
    return threadInfo
        .slice()
        .reverse()
        .map((message) => ({
            id: message.id,
            text: message.text,
            createdAt: message.created_at,
            updatedAt: message.updated_at,
            role: ROLE_MAPPER[message.sender_type] ?? Role.User,
            files: mapAttachmentsToFiles(message.attachments),
            status: message.status,
            correlationId: message.correlation_id,
        })) as TMessageContent[]
}
