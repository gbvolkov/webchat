import { Role, type TMessageContent } from './types'

type UnknownRecord = Record<string, unknown>

interface PasswordInterruptAnalysis {
  awaitingSecureReply: boolean
  maskedMessageIds: Set<string>
}

const asRecord = (value: unknown): UnknownRecord | undefined => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined
  }
  return value as UnknownRecord
}

export const extractInterruptFields = (metadata: unknown): UnknownRecord[] => {
  const metadataRecord = asRecord(metadata)
  const payload = asRecord(metadataRecord?.interrupt_payload)
  const fields = payload?.fields
  if (!Array.isArray(fields)) {
    return []
  }
  return fields
    .map((field) => asRecord(field))
    .filter((field): field is UnknownRecord => Boolean(field))
}

export const isPasswordPrompt = (metadata: unknown): boolean =>
  extractInterruptFields(metadata).some((field) => field.format === 'password')

export const maskSecret = (value: string): string => '•'.repeat(value.length)

export const analyzePasswordInterruptFlow = (
  messages: TMessageContent[],
): PasswordInterruptAnalysis => {
  const maskedMessageIds = new Set<string>()
  let awaitingSecureReply = false

  for (const message of messages) {
    if (message.role === Role.Ai && isPasswordPrompt(message.metadata)) {
      awaitingSecureReply = true
      continue
    }

    if (awaitingSecureReply && message.role === Role.User) {
      if (typeof message.id === 'string' && message.id.length > 0) {
        maskedMessageIds.add(message.id)
      }
      awaitingSecureReply = false
    }
  }

  return {
    awaitingSecureReply,
    maskedMessageIds,
  }
}
