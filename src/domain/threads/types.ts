export type SenderType = 'user' | 'assistant' | 'system'

export type MessageStatus = 'queued' | 'processing' | 'ready' | 'error'

export interface Pagination {
    total: number
    page: number
    limit: number
    has_more: boolean
}

export interface ThreadSummary {
    id: string
    owner_id: string
    title: string | null
    summary: string | null
    metadata: Record<string, unknown>
    is_deleted: boolean
    created_at: string
    updated_at: string
    deleted_at: string | null
}

export interface ThreadListResponse {
    items: ThreadSummary[]
    pagination: Pagination
}

export interface ThreadSearchResult {
    thread: ThreadSummary
    similarity?: number | null
}

export interface ThreadSearchResponse {
    items: ThreadSearchResult[]
    pagination: Pagination
    best_similarity?: number | null
    similarity_threshold?: number | null
    best_distance?: number | null
    distance_threshold?: number | null
    min_similarity?: number | null
}

export interface MessageDTO {
    id: string
    thread_id: string
    sender_id: string
    sender_type: SenderType
    status: MessageStatus
    text: string
    tokens_count?: number | null
    error_code?: string | null
    correlation_id?: string | null
    created_at: string
    updated_at: string
    attachments?: MessageAttachmentDTO[]
}

export interface MessageListResponse {
    items: MessageDTO[]
    pagination: Pagination
}

export interface ThreadDetail extends ThreadSummary {
    last_messages: MessageDTO[]
}

export interface MessageAttachmentDTO {
    id: string
    filename: string
    content_type: string
    data_base64?: string | null
    download_url?: string | null
    created_at: string
}

export type ThreadExportFormat = 'pdf' | 'markdown' | 'docx'
