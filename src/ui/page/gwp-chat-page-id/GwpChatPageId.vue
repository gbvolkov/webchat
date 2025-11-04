<script lang="ts" setup>
import { onMounted, ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { isAxiosError } from 'axios'
import { useAuthStore } from '@/store/auth-store'
import { mapThreadInfoToMessageContent } from '@/domain/threads/mapper'
import { useRoute } from 'vue-router'
import { Chat } from '@/ui/widget/chat'
import { ThreadsApi } from '@/domain/threads/api'
import { ChatApi } from '@/domain/chat/api'
import type { TMessageContent } from '@/ui/widget/chat/types'
import { ComponentStatus } from '@/consts/component-status'
import { FALLBACK_MODELS, FALLBACK_DEFAULT_MODEL, type ModelOption } from '@/config/llm'

const route = useRoute()

const componentStatus = ref<ComponentStatus>(ComponentStatus.INITIAL)

const authStore = useAuthStore()
const { t, locale } = useI18n()

const emptyChatPlaceholder = computed(() => {
  void locale.value
  const name = authStore.displayName || authStore.userId
  return t('pages.chatDetail.placeholders.empty', { name })
})

const messageHistory = ref<TMessageContent[]>([])
const threadMetadata = ref<Record<string, unknown>>({})
const currentThreadTitle = ref<string>('')
const cloneFallbackModels = () => FALLBACK_MODELS.map((model) => ({ ...model }))

const availableModels = ref<ModelOption[]>(cloneFallbackModels())
const selectedModel = ref<string>(FALLBACK_DEFAULT_MODEL)
const isModelsLoading = ref(false)
const modelsLoaded = ref(false)
const hasLoadedThread = ref(false)

const selectedModelOption = computed<ModelOption | undefined>(() =>
  availableModels.value.find((model) => model.id === selectedModel.value),
)

const chatId = computed(() => route.params.id as string | undefined)

const isLoading = computed(() => componentStatus.value === ComponentStatus.LOADING)
const hasError = computed(() => componentStatus.value === ComponentStatus.ERROR_LOADING)
const isEmpty = computed(() => messageHistory.value.length === 0)

const ensureSelectedModel = (preferred?: string | null) => {
  if (typeof preferred === 'string' && preferred.length > 0) {
    if (!availableModels.value.some((model) => model.id === preferred)) {
      availableModels.value = [{ id: preferred, label: preferred }, ...availableModels.value]
    }
    selectedModel.value = preferred
    return
  }

  if (!availableModels.value.length) {
    availableModels.value = cloneFallbackModels()
  }

  if (!selectedModel.value || !availableModels.value.some((model) => model.id === selectedModel.value)) {
    const nextModel = availableModels.value[0]
    if (nextModel) {
      selectedModel.value = nextModel.id
      return
    }
  }

  if (!selectedModel.value) {
    selectedModel.value = FALLBACK_DEFAULT_MODEL
  }
}

const loadModels = async () => {
  if (modelsLoaded.value) {
    ensureSelectedModel(threadMetadata.value?.['model'] as string | undefined)
    return
  }

  isModelsLoading.value = true
  try {
    const { data } = await ChatApi.getModels()
    const cards = Array.isArray(data.cards)
      ? data.cards.filter((card): card is { id: string; name?: string | null } => typeof card?.id === 'string')
      : []

    if (cards.length > 0) {
      availableModels.value = cards.map((card) => ({ id: card.id, label: card.name?.trim() || card.id }))
    } else if (Array.isArray(data.models) && data.models.length > 0) {
      availableModels.value = data.models
        .filter((model): model is string => typeof model === 'string' && model.length > 0)
        .map((id) => ({ id, label: id }))
    } else if (!availableModels.value.length) {
      availableModels.value = cloneFallbackModels()
      message.warning(t('pages.chatDetail.errors.fallbackModels'))
    }
  } catch (error) {
    availableModels.value = cloneFallbackModels()
    message.error(t('pages.chatDetail.errors.loadModels'))
    console.error('Failed to load models', error)
  } finally {
    modelsLoaded.value = true
    ensureSelectedModel(threadMetadata.value?.['model'] as string | undefined)
    isModelsLoading.value = false
  }
}

const loadThreadData = async () => {
  if (!chatId.value) {
    componentStatus.value = ComponentStatus.RESULT
    messageHistory.value = []
    return
  }

  componentStatus.value = ComponentStatus.LOADING

  try {
    const [messagesResponse, threadResponse] = await Promise.all([
      ThreadsApi.getThreadMessages(chatId.value).catch((error) => {
        console.error('Failed to load thread messages', error)
        return { data: { items: [], pagination: { total: 0, page: 1, limit: 20, has_more: false } } }
      }),
      ThreadsApi.getThread(chatId.value),
    ])

    messageHistory.value = mapThreadInfoToMessageContent(messagesResponse.data.items ?? [])
    threadMetadata.value = (threadResponse.data.metadata ?? {}) as Record<string, unknown>

    const newTitle = (threadResponse.data.title as string | undefined) ?? ''
    if (newTitle && newTitle !== currentThreadTitle.value) {
      currentThreadTitle.value = newTitle
      window.dispatchEvent(new CustomEvent('threads:refresh'))
    } else if (!newTitle) {
      currentThreadTitle.value = ''
    }

    const metadataModel = threadMetadata.value?.['model']
    ensureSelectedModel(typeof metadataModel === 'string' ? metadataModel : undefined)

    componentStatus.value = ComponentStatus.RESULT
    hasLoadedThread.value = true
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 404) {
      console.warn('Thread not found yet, showing empty state')
      messageHistory.value = []
      threadMetadata.value = {}
      currentThreadTitle.value = ''
      ensureSelectedModel()
      componentStatus.value = ComponentStatus.RESULT
      hasLoadedThread.value = true
      return
    }
    console.error('Failed to load thread data', error)
    componentStatus.value = ComponentStatus.ERROR_LOADING
  } finally {
    if (componentStatus.value === ComponentStatus.LOADING) {
      componentStatus.value = ComponentStatus.RESULT
    }
    if (!hasLoadedThread.value) {
      hasLoadedThread.value = true
    }
  }
}

const handleModelSelection = async (event: Event) => {
  if (!chatId.value) return

  const target = event.target as HTMLSelectElement
  const newModel = target.value
  if (!newModel || newModel === selectedModel.value) return

  const previousModel = selectedModel.value
  selectedModel.value = newModel

  const metadata: Record<string, unknown> = { ...threadMetadata.value, model: newModel }
  const selectedOption = availableModels.value.find((model) => model.id === newModel)
  if (selectedOption) {
    metadata.model_label = selectedOption.label
  } else {
    delete metadata.model_label
  }

  try {
    await ThreadsApi.updateThread(chatId.value, { metadata })
    threadMetadata.value = metadata
  } catch (error) {
    selectedModel.value = previousModel
    message.error(t('pages.chatDetail.errors.updateModel'))
    console.error('Failed to update thread model', error)
  }
}

onMounted(() => {
  loadModels()
  loadThreadData()
})

watch(chatId, (newChatId) => {
  if (!newChatId) return
  threadMetadata.value = {}
  currentThreadTitle.value = ''
  ensureSelectedModel()
  hasLoadedThread.value = false
  loadThreadData()
})

watch(availableModels, () => {
  ensureSelectedModel(threadMetadata.value?.['model'] as string | undefined)
})
</script>

<template>
  <div class="ChatPage__controls">
    <label class="ChatPage__controlLabel">
      {{ $t('pages.chatDetail.modelLabel') }}
      <select
          class="ChatPage__select"
          :value="selectedModel"
          :disabled="isLoading || !chatId || isModelsLoading || availableModels.length === 0"
          @change="handleModelSelection"
      >
        <option
            v-for="modelOption in availableModels"
            :key="modelOption.id"
            :value="modelOption.id"
        >
          {{ modelOption.label }}
        </option>
      </select>
    </label>
  </div>

  <Chat
      :history="messageHistory"
      :thread-id="chatId"
      :is-loading="isLoading"
      :model-id="selectedModel"
      :model-label="selectedModelOption?.label || selectedModel"
      @messageSent="loadThreadData"
  >
    <div
        v-if="isLoading && hasLoadedThread"
        class="ChatPage__placeholder"
    >
      {{ $t('pages.chatDetail.placeholders.loading') }}
    </div>
    <div
        v-else-if="hasError"
        class="ChatPage__placeholder ChatPage__placeholder_error"
    >
      {{ $t('pages.chatDetail.placeholders.loadError') }}
    </div>
    <div
        v-else-if="isEmpty"
        class="ChatPage__placeholder"
    >
        {{ emptyChatPlaceholder }}
    </div>
  </Chat>
</template>

<style lang="scss" scoped>
.ChatPage__controls {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.ChatPage__controlLabel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-family: var(--main_font);
  font-size: 14px;
  color: var(--gray_80);
}

.ChatPage__select {
  min-width: 220px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--gray_20);
  background-color: var(--gray_0);
  color: var(--gray_90);
}

.ChatPage__placeholder {
  font-family: var(--main_font);
  color: var(--gray_80);
  text-align: center;
  padding: 48px 0;
}

.ChatPage__placeholder_error {
  color: var(--error_50);
}
</style>











