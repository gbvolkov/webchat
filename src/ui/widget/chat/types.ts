import {MessageContent} from "deep-chat/dist/types/messages";

export enum Role {
    User = 'user',
    Ai = 'ai'
}

export type TMessageContent = Omit<MessageContent, 'role'> & {
    role: Role
    id?: string
    metadata?: Record<string, unknown>
    createdAt?: string
    updatedAt?: string
    status?: string
    correlationId?: string
}
