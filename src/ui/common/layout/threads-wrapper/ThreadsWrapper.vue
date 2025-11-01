<script lang="ts" setup>
import { onMounted, ref } from 'vue'
import { ThreadsApi } from '@/domain/threads/api'
import ThreadItem from './ThreadItem.vue'
import type { ThreadSummary } from '@/domain/threads/types'

const threadItems = ref<ThreadSummary[]>([])

interface Props {
  whenClickItem: (id: string) => void
  selectedThreadId: string
  whenDeleteThread?: (id: string) => Promise<void> | void
}

const props = defineProps<Props>()

const fetchThreads = async () => {
  try {
    const { data } = await ThreadsApi.getThreads()
    threadItems.value = data.items
  } catch (e) {
    console.error('Failed to load threads', e)
  }
}

onMounted(fetchThreads)

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
     />
  </div>
</template>
<style lang="scss">
</style>
