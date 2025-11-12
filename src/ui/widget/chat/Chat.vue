<script lang="ts" setup>
import 'deep-chat'
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import type { CSSProperties } from 'vue'
import type { Signals } from 'deep-chat/dist/types/handler'
import type { MessageFile } from 'deep-chat/dist/types/messageFile'
import { API_BASE_URL } from '@/config/api'
import type { IAttachmentUpload } from '@/domain/chat/api/types'
import { useAuthStore } from '@/store/auth-store'
import type { TMessageContent } from './types'
import { useI18n } from 'vue-i18n'

interface Props {
  history: TMessageContent[]
  threadId?: string
  isLoading?: boolean
  modelId: string
  modelLabel?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'messageSent'): void
}>()

const chatElementRef = ref<any>(null)
const authStore = useAuthStore()
const { t, locale } = useI18n()

const textInputPlaceholder = computed(() => {
  void locale.value
  return t('chat.input.placeholder')
})

const attachmentsButtonLabel = computed(() => {
  void locale.value
  return t('chat.input.attachments')
})

const streamErrorMessage = computed(() => {
  void locale.value
  return t('chat.errors.stream')
})

const hydratedHistory = ref<TMessageContent[]>([])
let historyHydrationToken = 0


const readFileAsBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const normalizeAttachment = async (raw: any): Promise<IAttachmentUpload | null> => {
  if (!raw) return null
  const hasFileCtor = typeof File !== 'undefined'
  const file: File | undefined = hasFileCtor
    ? raw?.file instanceof File
      ? raw.file
      : raw instanceof File
        ? raw
        : undefined
    : undefined
  const name = raw.name ?? raw.filename ?? file?.name
  const type = raw.type ?? raw.contentType ?? file?.type ?? 'application/octet-stream'

  let base64 = raw.base64 ?? raw.data ?? raw.data_base64
  if (!base64 && file) {
    base64 = await readFileAsBase64(file)
  }
  if (typeof base64 !== 'string') return null
  const [, encoded] = base64.split(',')
  const dataBase64 = encoded ?? base64
  if (!dataBase64) return null
  return {
    filename: name ?? 'attachment',
    content_type: type,
    data_base64: dataBase64,
  }
}

const normalizeAttachmentSources = (source: unknown): any[] => {
  if (!source) return []
  if (Array.isArray(source)) return source

  if (typeof FileList !== 'undefined' && source instanceof FileList) {
    return Array.from(source)
  }

  if (typeof source === 'object' && source !== null) {
    if (typeof Symbol !== 'undefined') {
      const iterable = (source as any)[Symbol.iterator]
      if (typeof iterable === 'function') {
        return Array.from(source as Iterable<unknown>)
      }
    }

    if ('length' in source && typeof (source as any).length === 'number') {
      return Array.from({ length: (source as any).length }, (_, index) => (source as any)[index])
    }
  }

  return [source]
}

const extractAttachments = async (sources: unknown): Promise<IAttachmentUpload[]> => {
  const items = normalizeAttachmentSources(sources)
  if (!items.length) return []
  const uploads = await Promise.all(items.map((item) => normalizeAttachment(item)))
  return uploads.filter((item): item is IAttachmentUpload => !!item)
}

const resolveApiBaseUrl = (): URL | null => {
  try {
    return new URL(API_BASE_URL)
  } catch {
    try {
      return new URL(API_BASE_URL, window.location.origin)
    } catch {
      return null
    }
  }
}

const apiBaseUrl = resolveApiBaseUrl()
const apiBaseForResolution = apiBaseUrl
  ? apiBaseUrl.toString().endsWith('/')
    ? apiBaseUrl.toString()
    : `${apiBaseUrl.toString()}/`
  : `${window.location.origin}/`
const apiOrigin = (() => {
  try {
    return new URL(apiBaseForResolution).origin
  } catch {
    return window.location.origin
  }
})()

const streamObjectUrls = new Set<string>()
let activeHistoryObjectUrls = new Set<string>()

const revokeObjectUrls = (bucket: Set<string>) => {
  bucket.forEach((url) => URL.revokeObjectURL(url))
  bucket.clear()
}

const releaseSecureObjectUrls = () => {
  revokeObjectUrls(streamObjectUrls)
  revokeObjectUrls(activeHistoryObjectUrls)
}

const isProtectedAttachmentUrl = (rawUrl: string): boolean => {
  try {
    const parsed = new URL(rawUrl)
    return parsed.origin === apiOrigin && parsed.pathname.includes('/attachments/')
  } catch {
    try {
      const fallback = new URL(rawUrl, window.location.origin)
      return fallback.origin === apiOrigin && fallback.pathname.includes('/attachments/')
    } catch {
      return false
    }
  }
}

interface AttachmentUrlOptions {
  bucket?: Set<string>
}

const buildAuthorizedObjectUrl = async (
  absoluteUrl: string,
  options?: AttachmentUrlOptions,
): Promise<string | undefined> => {
  try {
    const response = await authStore.authorizedFetch(absoluteUrl)
    if (!response.ok) {
      console.warn('Failed to download attachment', {
        url: absoluteUrl,
        status: response.status,
      })
      return undefined
    }
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const bucket = options?.bucket ?? streamObjectUrls
    bucket.add(objectUrl)
    return objectUrl
  } catch (error) {
    console.error('Failed to fetch attachment', absoluteUrl, error)
    return undefined
  }
}

const cloneMessageHistory = (source: TMessageContent[]): TMessageContent[] => {
  return source.map((message) => {
    const cloned: TMessageContent = { ...message }
    if (Array.isArray(message.files) && message.files.length > 0) {
      cloned.files = message.files
        .map((file) => {
          if (!file) return null
          return { ...file }
        })
        .filter((file): file is MessageFile => Boolean(file))
    }
    return cloned
  })
}

const buildHistoryPlaceholder = (source: TMessageContent[]): TMessageContent[] => {
  return cloneMessageHistory(source).map((message) => {
    if (!Array.isArray(message.files) || message.files.length === 0) {
      return message
    }
    const visibleFiles = message.files.filter((file) => {
      if (!file || typeof file.src !== 'string' || !file.src) return false
      return !isProtectedAttachmentUrl(file.src)
    })
    message.files = visibleFiles.length > 0 ? visibleFiles : undefined
    return message
  })
}

const hydrateHistoryMessages = async (messages: TMessageContent[]): Promise<void> => {
  const hydrationId = ++historyHydrationToken
  const cloned = cloneMessageHistory(messages)
  const pendingUrls = new Set<string>()
  const placeholder = buildHistoryPlaceholder(messages)
  hydratedHistory.value = placeholder

  try {
    await Promise.all(
      cloned.map(async (message) => {
        if (!Array.isArray(message.files) || message.files.length === 0) return
        await Promise.all(
          message.files.map(async (file, index) => {
            if (!file || typeof file.src !== 'string' || !file.src) return
            if (!isProtectedAttachmentUrl(file.src)) return
            const authorizedSrc = await buildAuthorizedObjectUrl(file.src, { bucket: pendingUrls })
            if (authorizedSrc) {
              message.files![index] = { ...file, src: authorizedSrc }
            }
          }),
        )
      }),
    )
  } finally {
    if (hydrationId === historyHydrationToken) {
      revokeObjectUrls(activeHistoryObjectUrls)
      activeHistoryObjectUrls = pendingUrls
      hydratedHistory.value = cloned
    } else {
      revokeObjectUrls(pendingUrls)
    }
  }
}

watch(
  () => props.history,
  (next) => {
    const messages = Array.isArray(next) ? next : []
    void hydrateHistoryMessages(messages)
  },
  { immediate: true },
)

const resolveAttachmentUrl = (rawUrl?: string | null): string | undefined => {
  if (!rawUrl) return undefined
  const trimmed = rawUrl.trim()
  if (!trimmed) return undefined
  try {
    return new URL(trimmed, apiBaseForResolution).toString()
  } catch {
    return trimmed
  }
}

const inferStreamFileType = (contentType?: string): MessageFile['type'] => {
  if (!contentType) return 'any'
  if (contentType.startsWith('image/')) return 'image'
  if (contentType.startsWith('audio/')) return 'audio'
  return 'any'
}

const normalizeStreamAttachmentFile = async (attachment: Record<string, unknown>): Promise<MessageFile | null> => {
  const filenameRaw = typeof attachment.filename === 'string' ? attachment.filename.trim() : ''
  const contentType = typeof attachment.content_type === 'string' ? attachment.content_type : ''
  const downloadUrl = typeof attachment.download_url === 'string' ? attachment.download_url.trim() : ''
  const dataBase64 = typeof attachment.data_base64 === 'string' ? attachment.data_base64.trim() : ''
  const name = filenameRaw || 'attachment'

  let src: string | undefined
  if (downloadUrl) {
    const absoluteUrl = resolveAttachmentUrl(downloadUrl)
    if (absoluteUrl) {
      if (isProtectedAttachmentUrl(absoluteUrl)) {
        src = await buildAuthorizedObjectUrl(absoluteUrl)
      } else {
        src = absoluteUrl
      }
    }
  }
  if (!src && dataBase64) {
    const mime = contentType || 'application/octet-stream'
    src = `data:${mime};base64,${dataBase64}`
  }
  if (!src) return null

  return {
    name,
    type: inferStreamFileType(contentType),
    src,
  }
}

const FORM_DATA_MESSAGE_RE = /^message(\d+)$/i

interface ParsedFormDataPayload {
  text?: string
  files: File[]
}

const isFileLike = (value: unknown): value is File =>
  typeof File !== 'undefined' && value instanceof File

const collectFormDataFiles = (formData: FormData): File[] => {
  const collected: File[] = []

  if (typeof formData.getAll === 'function') {
    const values = formData.getAll('files')
    values.forEach((value) => {
      if (isFileLike(value)) {
        collected.push(value)
      }
    })
  }

  if (!collected.length) {
    formData.forEach((value, key) => {
      if (key === 'files' && isFileLike(value) && !collected.includes(value)) {
        collected.push(value)
      }
    })
  }

  return collected
}

const parseFormDataPayload = (formData: FormData): ParsedFormDataPayload => {
  const files = collectFormDataFiles(formData)
  const messageChunks: Array<{ order: number; payload: any }> = []

  formData.forEach((value, key) => {
    if (key === 'files') {
      return
    }

    const match = key.match(FORM_DATA_MESSAGE_RE)
    if (!match || typeof value !== 'string') return

    const order = Number.parseInt(match[1], 10)
    if (Number.isNaN(order)) return
    try {
      messageChunks.push({ order, payload: JSON.parse(value) })
    } catch {
      // ignore malformed chunk
    }
  })

  messageChunks.sort((a, b) => a.order - b.order)
  const lastChunk = messageChunks[messageChunks.length - 1]?.payload
  const text = typeof lastChunk?.text === 'string' ? lastChunk.text : undefined

  return { text, files }
}

const isFormDataPayload = (value: unknown): value is FormData => {
  if (typeof FormData !== 'undefined' && value instanceof FormData) {
    return true
  }

  return (
    Boolean(value) &&
    typeof value === 'object' &&
    typeof (value as FormData).append === 'function' &&
    typeof (value as FormData).getAll === 'function' &&
    typeof (value as FormData).forEach === 'function'
  )
}

const sendStreamingMessage = async (
  threadId: string,
  textContent: string,
  attachments: IAttachmentUpload[],
  signals: Signals,
): Promise<boolean> => {
  const controller = new AbortController()
  signals.stopClicked.listener = () => controller.abort()

  await authStore.ensureInitialized()
  const senderId = authStore.userId
  if (!senderId) {
    throw new Error(t('chat.errors.unauthorized'))
  }

  const requestPayload = {
    sender_id: senderId,
    sender_type: 'user',
    text: textContent,
    model: props.modelId,
    model_label: props.modelLabel,
    attachments,
  }

  const response = await authStore.authorizedFetch(`${API_BASE_URL}/threads/${threadId}/messages/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(requestPayload),
    signal: controller.signal,
  })

  if (!response.ok) {
    let message = streamErrorMessage.value
    try {
      const errorPayload = await response.json()
      const detail = errorPayload?.detail ?? errorPayload?.error?.message
      if (typeof detail === 'string' && detail.trim().length > 0) {
        message = detail
      }
    } catch {
      // ignore JSON parse failure
    }
    throw new Error(message)
  }

  const bodyStream = response.body
  if (!bodyStream) {
    throw new Error(streamErrorMessage.value)
  }

  const reader = bodyStream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let assistantText = ''
  let hasAssistantMessage = false
  let assistantRole: string | undefined
  let streamingFinished = false
  const assistantFiles: MessageFile[] = []
  const assistantFileMap = new Map<string, MessageFile>()

  const syncAssistantFiles = () => {
    assistantFiles.splice(0, assistantFiles.length, ...assistantFileMap.values())
  }

  const upsertAssistantFiles = async (candidateList: unknown): Promise<boolean> => {
    if (!Array.isArray(candidateList)) return false
    let changed = false
    for (const candidate of candidateList) {
      if (!candidate || typeof candidate !== 'object') continue
      const normalized = await normalizeStreamAttachmentFile(candidate as Record<string, unknown>)
      if (!normalized) continue
      const rawId = (candidate as Record<string, unknown>).id
      const key =
        (typeof rawId === 'string' && rawId.trim().length > 0 && rawId.trim()) ||
        normalized.src ||
        `${normalized.name}-${assistantFileMap.size}`
      if (!assistantFileMap.has(key)) {
        assistantFileMap.set(key, normalized)
        changed = true
      }
    }
    if (changed) {
      syncAssistantFiles()
    }
    return changed
  }

  const appendContent = (content: unknown): boolean => {
    if (typeof content === 'string') {
      if (!content) return false
      assistantText += content
      return true
    }
    if (Array.isArray(content)) {
      let appended = false
      for (const part of content) {
        if (typeof part === 'string') {
          if (!part) continue
          assistantText += part
          appended = true
        } else if (part && typeof part === 'object') {
          const maybeText = (part as Record<string, unknown>).text
          if (typeof maybeText === 'string' && maybeText) {
            assistantText += maybeText
            appended = true
          }
        }
      }
      return appended
    }
    if (content && typeof content === 'object') {
      const maybeText = (content as Record<string, unknown>).text
      if (typeof maybeText === 'string' && maybeText) {
        assistantText += maybeText
        return true
      }
    }
    return false
  }

  const ensureAssistantMessage = async () => {
    const payload: { role: string; text: string; overwrite?: boolean; files?: MessageFile[] } = {
      role: assistantRole ?? 'assistant',
      text: assistantText,
    }
    if (assistantFiles.length) {
      payload.files = assistantFiles.map((file) => ({ ...file }))
    }
    if (hasAssistantMessage) {
      payload.overwrite = true
    }
    await signals.onResponse(payload)
    hasAssistantMessage = true
  }

  const processPayload = async (payload: any) => {
    if (!payload || typeof payload !== 'object') return

    if (payload.error && typeof payload.error === 'object') {
      const message =
        typeof payload.error.message === 'string' && payload.error.message.trim().length > 0
            ? payload.error.message
            : streamErrorMessage.value
      throw new Error(message)
    }

    let chunkHasContent = false
    let chunkHasRoleHint = false
    let chunkHasFiles = false

    const metadata = (payload as Record<string, unknown>).message_metadata
    if (metadata && typeof metadata === 'object') {
      const attachments = (metadata as Record<string, unknown>).attachments
      chunkHasFiles = (await upsertAssistantFiles(attachments)) || chunkHasFiles
    }

    const choices = Array.isArray(payload.choices) ? payload.choices : []
    for (const choice of choices) {
      if (!choice || typeof choice !== 'object') {
        continue
      }
      const delta = (choice as Record<string, unknown>).delta as Record<string, unknown> | undefined
      if (delta) {
        const role = delta.role
        if (typeof role === 'string' && role) {
          assistantRole = role
          if (!hasAssistantMessage) {
            chunkHasRoleHint = true
          }
        }
        if ('content' in delta) {
          chunkHasContent = appendContent(delta.content) || chunkHasContent
        }
      }

      const message = (choice as Record<string, unknown>).message as
        | Record<string, unknown>
        | undefined
      if (message && 'content' in message) {
        chunkHasContent = appendContent(message.content) || chunkHasContent
      }
    }

    if (chunkHasContent || chunkHasFiles || (!hasAssistantMessage && chunkHasRoleHint)) {
      await ensureAssistantMessage()
    }
  }

  const processBuffer = async () => {
    while (!streamingFinished) {
      const separatorIndex = buffer.indexOf('\n\n')
      if (separatorIndex === -1) {
        return
      }
      const rawEvent = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      if (!rawEvent.trim()) {
        continue
      }

      const dataLines = rawEvent
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())

      for (const dataLine of dataLines) {
        if (!dataLine) {
          continue
        }
        if (dataLine === '[DONE]') {
          streamingFinished = true
          break
        }
        let parsed: any
        try {
          parsed = JSON.parse(dataLine)
        } catch (error) {
          console.warn('Failed to parse streaming chunk', error)
          continue
        }
        await processPayload(parsed)
        if (streamingFinished) {
          break
        }
      }
    }
  }

  try {
    while (!streamingFinished) {
      const { value, done } = await reader.read()
      if (done) {
        buffer += decoder.decode()
        await processBuffer()
        break
      }
      if (value) {
        buffer += decoder.decode(value, { stream: true })
        await processBuffer()
      }
    }

    if (assistantText && !hasAssistantMessage) {
      await ensureAssistantMessage()
    }

    await signals.onResponse({})
    return true
  } finally {
    signals.stopClicked.listener = () => {}
    try {
      reader.releaseLock()
    } catch {
      // ignore release failures
    }
  }
}

const defineConnectFn = () => {
  if (!chatElementRef.value?.connect) return

  chatElementRef.value.connect = {
    handler: async (body: any, signals: Signals) => {
      if (!props.threadId) return

      let textMessage: string | undefined
      let attachmentSources: unknown
      let shouldEmitSent = false

      try {
        if (isFormDataPayload(body)) {
          const parsed = parseFormDataPayload(body)
          textMessage = parsed.text
          attachmentSources = parsed.files
        } else {
          const messages = body?.messages
          textMessage = messages?.[0]?.text
          attachmentSources = body?.files
        }

        let preparedText = typeof textMessage === 'string' ? textMessage : ''
        const attachments = await extractAttachments(attachmentSources)
        if (!preparedText.trim()) {
          if (!attachments.length) {
            return
          }
          preparedText = 'Process as expected.'
        }
        const success = await sendStreamingMessage(
          props.threadId,
          preparedText,
          attachments,
          signals,
        )
        shouldEmitSent = success
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          shouldEmitSent = false
          return
        }

        console.error('Failed to stream assistant response', error)
        const message =
          error instanceof Error &&
          typeof error.message === 'string' &&
          error.message.trim().length > 0
            ? error.message
            : streamErrorMessage.value
        await signals.onResponse({ error: message })
        shouldEmitSent = false
      } finally {
        if (shouldEmitSent) {
          emit('messageSent')
        }
      }
    },
  }
}

onMounted(defineConnectFn)
onBeforeUnmount(() => {
  releaseSecureObjectUrls()
})

const textInputContainerStyles: CSSProperties = {
  borderRadius: '16px',
  width: '78%',
  height: '120px',
  marginLeft: '-15px',
  boxShadow: 'initial',
  backgroundColor: 'var(--gray_0)',
  border: '1px solid var(--gray_10)',
  padding: '16px',
}

const textInputStyles: CSSProperties = {
  padding: '0px',
  paddingLeft: '0px',
  paddingRight: '0px',
}

const introPanelStyle: CSSProperties = {
  position: 'initial',
  display: 'block',
  padding: '60px 160px',
  textAlign: 'center',
}

const inputPlaceholderStyle: CSSProperties = {
  color: 'var(--gray_40)',
}

const aiBubbleStyles: CSSProperties = {
  backgroundColor: 'initial',
  color: 'var(--gray_100)',
  borderRadius: '8px',
}

const userBubbleStyles: CSSProperties = {
  backgroundColor: 'var(--gray_0)',
  color: 'var(--gray_100)',
  borderRadius: '8px',
}
</script>

<template>
  <deep-chat
    ref="chatElementRef"
    class="Chat"
    :connect="{}"
    :history="hydratedHistory"
    :introPanelStyle="introPanelStyle"
    :textInput="{
      styles: {
        container: textInputContainerStyles,
        text: textInputStyles,
      },
      placeholder: {
        text: textInputPlaceholder,
        style: inputPlaceholderStyle,
      },
      disabled: props.isLoading,
    }"
    :submit-button-styles="{
      submit: {
        container: {
          default: { backgroundColor: 'initial' },
          hover: { backgroundColor: 'initial' },
          click: { backgroundColor: 'initial' },
        },
        svg: {
          content:
            '<svg width=&quot;10&quot; height=&quot;12&quot; viewBox=&quot;0 0 10 12&quot; fill=&quot;none&quot; xmlns=&quot;http://www.w3.org/2000/svg&quot;>\n' +
            '    <path d=&quot;M5 1.5L5 10.5M5 1.5L1 5.35714M5 1.5L9 5.35714&quot; stroke=&quot;#495B69&quot; stroke-width=&quot;1.4&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;/>\n' +
            '</svg>\n',
        },
      },
    }"
    :mixedFiles="{ button: { position: 'inside-left', text: attachmentsButtonLabel } }"
    :messageStyles="{
      default: {
        ai: {
          bubble: aiBubbleStyles,
        },
        user: {
          bubble: userBubbleStyles,
        },
      },
    }"
  >
    <slot />
  </deep-chat>
</template>

<style lang="scss" scoped>
.Chat {
  width: 100% !important;
  height: 100% !important;
  border: none !important;
}
</style>




