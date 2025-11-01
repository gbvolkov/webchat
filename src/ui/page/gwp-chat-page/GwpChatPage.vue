<script lang="ts" setup>
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/store/auth-store'
import { Chat } from '@/ui/widget/chat'
import type { TMessageContent } from '@/ui/widget/chat/types'
import { FALLBACK_DEFAULT_MODEL } from '@/config/llm'
import { ChatApi } from '@/domain/chat/api'

const authStore = useAuthStore()

const messageHistory = ref<TMessageContent[]>([])
const defaultModel = ref<string>(FALLBACK_DEFAULT_MODEL)

const loadModels = async () => {
  try {
    const { data } = await ChatApi.getModels()
    const cards = Array.isArray(data.cards)
      ? data.cards.filter((card): card is { id: string; name?: string | null } => typeof card?.id === 'string')
      : []

    if (cards.length > 0) {
      defaultModel.value = cards[0].id
      return
    }

    const models = Array.isArray(data.models)
      ? data.models.filter((model): model is string => typeof model === 'string' && model.length > 0)
      : []

    if (models.length > 0) {
      defaultModel.value = models[0]
    } else if (!defaultModel.value) {
      defaultModel.value = FALLBACK_DEFAULT_MODEL
    }
  } catch (error) {
    if (!defaultModel.value) {
      defaultModel.value = FALLBACK_DEFAULT_MODEL
    }
    message.error('Не удалось загрузить список моделей')
    console.error('Failed to load models', error)
  }
}

onMounted(loadModels)
</script>

<template>
  <Chat
      :history="messageHistory"
      :model-id="defaultModel"
      :model-label="defaultModel"
  >
    <div class="ChatPage__placeholder">
      Привет, {{ authStore.userName }}! Выберите чат из списка слева или создайте новый, чтобы начать беседу.
    </div>
  </Chat>
</template>

<style lang="scss" scoped>
.ChatPage__placeholder {
  font-family: var(--main_font);
  color: var(--gray_80);
  text-align: center;
  padding: 48px 0;
}
</style>
