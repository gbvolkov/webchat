export interface ISendMessageRequest {
    sender_id: string
    text: string
    sender_type?: 'user' | 'assistant' | 'system'
    model?: string
    model_label?: string
    attachments?: IAttachmentUpload[]
}

export interface IModelCard {
    id: string
    name?: string | null
}

export interface IModelsResponse {
    models: string[]
    cards?: IModelCard[]
}

export interface IAttachmentUpload {
    filename: string
    content_type?: string
    data_base64: string
}
