import {MessageContent} from "deep-chat/dist/types/messages";

export enum Role {
    User = 'user',
    Ai = 'ai'
}

export type TMessageContent = Omit<MessageContent, 'role'> & { role: Role }