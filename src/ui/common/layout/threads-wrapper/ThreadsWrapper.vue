<script lang="ts" setup>
import { onMounted, ref, watch } from 'vue'
import { ThreadsApi } from '@/domain/threads/api'
import ThreadItem from './ThreadItem.vue'
import type { ThreadSummary, ThreadExportFormat } from '@/domain/threads/types'
import { useAuthStore } from '@/store/auth-store'

const threadItems = ref<ThreadSummary[]>([])
const authStore = useAuthStore()

interface Props {
  whenClickItem: (id: string) => void
  selectedThreadId: string
  whenDeleteThread?: (id: string) => Promise<void> | void
  whenExportThread?: (id: string, format: ThreadExportFormat) => Promise<void> | void
}

const props = defineProps<Props>()

const fetchThreads = async () => {
  if (!authStore.hasSession) {
    threadItems.value = []
    return
  }
  try {
    const { data } = await ThreadsApi.getThreads()
    threadItems.value = data.items
  } catch (e) {
    if (authStore.hasSession) {
      console.error('Failed to load threads', e)
    }
  }
}

onMounted(() => {
  if (authStore.hasSession) {
    void fetchThreads()
  }
})

watch(
  () => authStore.hasSession,
  (hasSession) => {
    if (hasSession) {
      void fetchThreads()
    } else {
      threadItems.value = []
    }
  },
)

defineExpose({
  refresh: fetchThreads,
})

const handleDeleteThread = async (id: string) => {
  try {
    await props.whenDeleteThread?.(id)
  } catch (error) {
    console.error('Failed to delete thread', error)
  }
}
</script>

<template>
  <div class="ThreadsWrapper">
     <ThreadItem
         v-for="threadItem in threadItems"
         :key="threadItem.id"
         :thread-item="threadItem"
         :is-selected="threadItem.id === props.selectedThreadId"
         :when-click-thread-item="() => whenClickItem(threadItem.id)"
         :when-delete-thread="handleDeleteThread"
         :when-export-thread="props.whenExportThread"
     />
  </div>
</template>
<style lang="scss">
</style>
