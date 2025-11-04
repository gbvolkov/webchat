<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { ThreadsApi } from '@/domain/threads/api'
import type { ThreadSearchResult } from '@/domain/threads/types'
import { ChatApi } from '@/domain/chat/api'
import { FALLBACK_MODELS, type ModelOption } from '@/config/llm'
import { Routes } from '@/config/router/routes'

const router = useRouter()
const { t } = useI18n()

const phrase = ref<string>('')
const selectedModel = ref<string | undefined>(undefined)
const availableModels = ref<ModelOption[]>(cloneFallbackModels())
const isLoading = ref(false)
const hasSearched = ref(false)
const searchResults = ref<ThreadSearchResult[]>([])

const totalResults = ref<number>(0)
const bestSimilarity = ref<number | null>(null)
const similarityThreshold = ref<number | null>(null)
const bestDistance = ref<number | null>(null)
const distanceThreshold = ref<number | null>(null)
const minSimilarity = ref<number | null>(null)

function cloneFallbackModels(): ModelOption[] {
  return FALLBACK_MODELS.map((model) => ({ ...model }))
}

const selectedModelOption = computed(() => {
  if (!selectedModel.value) return undefined
  return availableModels.value.find((model) => model.id === selectedModel.value)
})

const canSearch = computed(() => phrase.value.trim().length > 0)

const loadModels = async () => {
  try {
    const { data } = await ChatApi.getModels()
    const cards = Array.isArray(data.cards)
      ? data.cards.filter((card): card is { id: string; name?: string | null } => typeof card?.id === 'string')
      : []

    if (cards.length > 0) {
      availableModels.value = cards.map((card) => ({
        id: card.id,
        label: card.name?.trim() || card.id,
      }))
    } else if (Array.isArray(data.models) && data.models.length > 0) {
      availableModels.value = data.models
        .filter((model): model is string => typeof model === 'string' && model.trim().length > 0)
        .map((id) => ({ id, label: id }))
    } else {
      availableModels.value = cloneFallbackModels()
    }
  } catch (error) {
    availableModels.value = cloneFallbackModels()
    console.error('Failed to load models for search', error)
  }
}

const handleSearch = async () => {
  if (!canSearch.value) {
    message.warning(t('pages.chatSearch.notifications.phraseRequired'))
    return
  }

  isLoading.value = true
  hasSearched.value = true

  try {
    const payload: { phrase: string; model_id?: string } = {
      phrase: phrase.value.trim(),
    }
    if (selectedModel.value) {
      payload.model_id = selectedModel.value
    }

    const { data } = await ThreadsApi.searchThreads(payload)
    searchResults.value = data.items
    totalResults.value = data.pagination.total
    bestSimilarity.value = data.best_similarity ?? null
    similarityThreshold.value = data.similarity_threshold ?? null
    bestDistance.value = data.best_distance ?? null
    distanceThreshold.value = data.distance_threshold ?? null
    minSimilarity.value = data.min_similarity ?? null
  } catch (error) {
    message.error(t('pages.chatSearch.notifications.searchFailed'))
    console.error('Search error', error)
  } finally {
    isLoading.value = false
  }
}

const handleOpenThread = (threadId: string) => {
  if (!threadId) return
  router.push({ name: Routes.ChatDetail, params: { id: threadId } })
}

const handleDeleteThread = (threadId: string) => {
  Modal.confirm({
    title: t('common.confirmations.deleteChat.title'),
    content: t('common.confirmations.deleteChat.description'),
    okText: t('common.confirmations.deleteChat.confirm'),
    cancelText: t('common.confirmations.deleteChat.cancel'),
    okType: 'danger',
    async onOk() {
      try {
        await ThreadsApi.deleteThread(threadId)
        message.success(t('pages.chatSearch.notifications.deleteSuccess'))
        await handleSearch()
        window.dispatchEvent(new CustomEvent('threads:refresh'))
      } catch (error) {
        message.error(t('pages.chatSearch.notifications.deleteFailed'))
        console.error('Failed to delete thread from search', error)
      }
    },
  })
}

const handleReset = () => {
  phrase.value = ''
  selectedModel.value = undefined
  searchResults.value = []
  totalResults.value = 0
  bestSimilarity.value = null
  similarityThreshold.value = null
  bestDistance.value = null
  distanceThreshold.value = null
  minSimilarity.value = null
  hasSearched.value = false
}

onMounted(loadModels)

const formatSimilarity = (value?: number | null) => {
  if (value === undefined || value === null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

const formatDistance = (value?: number | null) => {
  if (value === undefined || value === null) return '—'
  return value.toFixed(4)
}
</script>

<template>
  <section class="SearchPage">
    <header class="SearchPage__header">
      <h1 class="SearchPage__title">{{ $t('pages.chatSearch.title') }}</h1>
      <p class="SearchPage__subtitle">
        {{ $t('pages.chatSearch.subtitle') }}
      </p>
    </header>

    <form class="SearchPage__form" @submit.prevent="handleSearch">
      <label class="SearchPage__field">
        <span>{{ $t('pages.chatSearch.phraseLabel') }}</span>
        <a-input
            v-model:value="phrase"
            :placeholder="$t('pages.chatSearch.phrasePlaceholder')"
            allow-clear
            @keyup.enter="handleSearch"
        />
      </label>

      <label class="SearchPage__field">
        <span>{{ $t('pages.chatSearch.modelLabel') }}</span>
        <a-select
        v-model:value="selectedModel"
            :options="availableModels"
            allow-clear
            :placeholder="$t('pages.chatSearch.modelPlaceholder')"
            :field-names="{ label: 'label', value: 'id' }"
        />
      </label>

      <div class="SearchPage__actions">
        <a-button
            type="primary"
            :disabled="!canSearch"
            :loading="isLoading"
            @click="handleSearch"
        >
          {{ $t('common.actions.search') }}
        </a-button>
        <a-button
            type="default"
            @click="handleReset"
        >
          {{ $t('common.actions.reset') }}
        </a-button>
      </div>
    </form>

    <section class="SearchPage__results">
      <div class="SearchPage__resultsHeader">
        <span>{{ $t('pages.chatSearch.results.title') }}</span>
        <span class="SearchPage__resultsCount">
          {{ totalResults }}
        </span>
      </div>

      <div v-if="isLoading" class="SearchPage__placeholder">
        {{ $t('pages.chatSearch.results.loading') }}
      </div>

      <div v-else-if="hasSearched && searchResults.length === 0" class="SearchPage__placeholder">
        {{ $t('pages.chatSearch.results.empty') }}
      </div>

      <div
          v-if="searchResults.length > 0 && (bestSimilarity !== null || minSimilarity !== null)"
          class="SearchPage__metrics"
      >
        <span v-if="bestSimilarity !== null">{{ $t('pages.chatSearch.results.metrics.bestSimilarity', { value: formatSimilarity(bestSimilarity) }) }}</span>
        <span v-if="similarityThreshold !== null">{{ $t('pages.chatSearch.results.metrics.similarityThreshold', { value: formatSimilarity(similarityThreshold) }) }}</span>
        <span v-if="minSimilarity !== null">{{ $t('pages.chatSearch.results.metrics.minSimilarity', { value: formatSimilarity(minSimilarity) }) }}</span>
        <span v-if="bestDistance !== null">{{ $t('pages.chatSearch.results.metrics.bestDistance', { value: formatDistance(bestDistance) }) }}</span>
        <span v-if="distanceThreshold !== null">{{ $t('pages.chatSearch.results.metrics.distanceThreshold', { value: formatDistance(distanceThreshold) }) }}</span>
      </div>

      <ul v-if="searchResults.length > 0" class="SearchPage__list">
        <li
            v-for="result in searchResults"
            :key="result.thread.id"
            class="SearchPage__listItem"
        >
          <div class="SearchPage__listContent" @click="handleOpenThread(result.thread.id)">
            <div class="SearchPage__listTitle">
              {{ result.thread.title || ('pages.chatSearch.results.card.untitled') }}
            </div>
            <div class="SearchPage__listMeta">`n                {{ $t('pages.chatSearch.results.card.model', { label: result.thread.metadata?.model_label || result.thread.metadata?.model || $t('pages.chatSearch.results.card.modelUnknown') }) }}`n              </div>
            <div class="SearchPage__listMeta SearchPage__listMeta_secondary">`n                {{ $t('pages.chatSearch.results.card.similarity', { value: formatSimilarity(result.similarity) }) }}`n              </div>
          </div>
          <a-button
              type="link"
              danger
              class="SearchPage__delete"
              @click.stop="handleDeleteThread(result.thread.id)"
          > {{ $t('pages.chatSearch.results.card.delete') }} </a-button>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped lang="scss">
.SearchPage {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.SearchPage__header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.SearchPage__title {
  font-size: 24px;
  margin: 0;
}

.SearchPage__subtitle {
  margin: 0;
  color: var(--gray_70);
}

.SearchPage__form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  align-items: end;
}

.SearchPage__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  color: var(--gray_80);
}

.SearchPage__actions {
  display: flex;
  gap: 12px;
}

.SearchPage__results {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.SearchPage__resultsHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}

.SearchPage__metrics {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--gray_70);
}

.SearchPage__resultsCount {
  color: var(--gray_70);
}

.SearchPage__placeholder {
  padding: 32px;
  text-align: center;
  color: var(--gray_70);
  border: 1px dashed var(--gray_30);
  border-radius: 12px;
}

.SearchPage__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.SearchPage__listItem {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border: 1px solid var(--gray_20);
  border-radius: 12px;
  background-color: var(--gray_white);
}

.SearchPage__listItem:hover {
  border-color: var(--brand_40);
}

.SearchPage__listContent {
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
}

.SearchPage__listTitle {
  font-weight: 600;
}

.SearchPage__listMeta {
  font-size: 13px;
  color: var(--gray_70);
}

.SearchPage__listMeta_secondary {
  color: var(--gray_60);
}

.SearchPage__delete {
  font-size: 13px;
}
</style>


















