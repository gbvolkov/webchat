<script lang="ts" setup>
import { reactive, ref, watch, computed, onMounted, onBeforeUnmount } from 'vue'
import folder from '@/assets/icons/menu/folder.svg'
import figures from '@/assets/icons/menu/figures.svg'
import dialog from '@/assets/icons/menu/dialog.svg'
import search from '@/assets/icons/menu/search.svg'

import logo from '@/assets/icons/menu/logo.svg'
import assistant from '@/assets/icons/menu/assistant.svg'
import MenuItem from './MenuItem.vue'
import { Routes } from '@/config/router/routes'
import { useRoute, useRouter } from 'vue-router'
import { ThreadsWrapper } from '@/ui/common/layout/threads-wrapper'
import { EventKeys } from '@/ui/common/layout/menu/types'
import { ThreadsApi } from '@/domain/threads/api'
import { message, Modal } from 'ant-design-vue'

const route = useRoute()
const router = useRouter()

const selectedKey = ref<string>(route.name as string)
const threadsWrapperRef = ref<InstanceType<typeof ThreadsWrapper> | null>(null)

const selectedThreadId = computed((): string => {
  return selectedKey.value?.includes(Routes.ChatDetail)
    ? (route.params.id as string) || ''
    : ''
})

watch(
  () => route.name,
  (newRouteName) => newRouteName && (selectedKey.value = newRouteName as string),
  { immediate: true, deep: true },
)

interface IMenuItem {
  label: string
  key: EventKeys
  icon: string
  type?: 'group'
}

function getItem(
  label: string,
  key: EventKeys,
  icon: string,
  type?: 'group',
): IMenuItem {
  return {
    key,
    icon,
    label,
    type,
  }
}

const CHAT_LABELS: Record<EventKeys, string> = {
  [EventKeys.NewChat]: 'Новый чат',
  [EventKeys.ChatSearch]: 'Поиск по чатам',
  [EventKeys.ChatHistory]: 'История',
  [EventKeys.ChatLibrary]: 'Библиотека',
}

const CHAT_ICONS: Record<EventKeys, string> = {
  [EventKeys.NewChat]: dialog,
  [EventKeys.ChatSearch]: search,
  [EventKeys.ChatHistory]: folder,
  [EventKeys.ChatLibrary]: figures,
}

const EVENT_KEY_TO_ROUTE_ADAPTER: Partial<Record<EventKeys, Routes>> = {
  [EventKeys.ChatHistory]: Routes.ChatsHistory,
  [EventKeys.ChatLibrary]: Routes.ChatsLibrary,
}

const items = reactive<IMenuItem[]>([
  getItem(CHAT_LABELS[EventKeys.NewChat], EventKeys.NewChat, CHAT_ICONS[EventKeys.NewChat]),
  getItem(CHAT_LABELS[EventKeys.ChatSearch], EventKeys.ChatSearch, CHAT_ICONS[EventKeys.ChatSearch]),
  getItem(CHAT_LABELS[EventKeys.ChatHistory], EventKeys.ChatHistory, CHAT_ICONS[EventKeys.ChatHistory]),
  getItem(CHAT_LABELS[EventKeys.ChatLibrary], EventKeys.ChatLibrary, CHAT_ICONS[EventKeys.ChatLibrary]),
])

const createNewThread = async () => {
  try {
    const { data } = await ThreadsApi.createThread()
    await threadsWrapperRef.value?.refresh()
    selectedKey.value = Routes.ChatDetail
    router.push({
      name: Routes.ChatDetail,
      params: { id: data.id },
    })
  } catch (error) {
    message.error('Не удалось создать новый чат')
    console.error(error)
  }
}

const actionByEventKey: Record<EventKeys, () => void> = {
  [EventKeys.ChatLibrary]: () => router.push({ name: Routes.ChatsLibrary }),
  [EventKeys.ChatHistory]: () => router.push({ name: Routes.ChatsHistory }),
  [EventKeys.ChatSearch]: () => router.push({ name: Routes.ChatSearch }),
  [EventKeys.NewChat]: createNewThread,
}

const whenMenuItemClick = (value: EventKeys) => {
  actionByEventKey[value]()
}

const whenClickThread = (id: string) => {
  selectedKey.value = `${Routes.ChatDetail}/${id}`
  router.push({
    name: Routes.ChatDetail,
    params: { id },
  })
}

const whenClickLogo = () => router.push({ name: Routes.Chat })

const handleDeleteThread = (id: string) => {
  Modal.confirm({
    title: 'Удалить чат?',
    content: 'Чат будет скрыт из списка истории.',
    okText: 'Удалить',
    cancelText: 'Отмена',
    okType: 'danger',
    async onOk() {
      try {
        await ThreadsApi.deleteThread(id)
        message.success('Чат удалён')
        await threadsWrapperRef.value?.refresh()
        const { data } = await ThreadsApi.getThreads()
        if (data.items.length > 0) {
          const nextThread = data.items[0]
          selectedKey.value = Routes.ChatDetail
          router.push({ name: Routes.ChatDetail, params: { id: nextThread.id } })
        } else {
          selectedKey.value = Routes.Chat
          router.push({ name: Routes.Chat })
        }
        window.dispatchEvent(new CustomEvent('threads:refresh'))
      } catch (error) {
        message.error('Не удалось удалить чат')
        console.error('Failed to delete thread', error)
      }
    },
  })
}

const refreshThreads = () => threadsWrapperRef.value?.refresh()

onMounted(() => {
  window.addEventListener('threads:refresh', refreshThreads)
})

onBeforeUnmount(() => {
  window.removeEventListener('threads:refresh', refreshThreads)
})
</script>

<template>
  <aside class="MenuWrapper">
    <button
        class="MenuWrapper__logoAndAssistant"
        @click="whenClickLogo"
    >
      <div class="MenuWrapper__logoAndAssistantWrapper">
        <img
            :src="logo"
            alt="logo"
            class="MenuWrapper__icon"
        >
        <img
            :src="assistant"
            alt="assistant"
            class="MenuWrapper__icon"
        >
      </div>
    </button>

    <div class="MenuWrapper__mainItemsWrapper">
      <MenuItem
          v-for="({ label, key, icon }, index) in items"
          :key="index"
          :label="label"
          :leftContentIcon="icon"
          :whenClick="() => whenMenuItemClick(key)"
          :selectedRoute="`${selectedKey}`"
          :eventKey="EVENT_KEY_TO_ROUTE_ADAPTER[key] || key"
      />
    </div>

    <ThreadsWrapper
        ref="threadsWrapperRef"
        :whenClickItem="whenClickThread"
        :selectedThreadId="selectedThreadId"
        :whenDeleteThread="handleDeleteThread"
    />
  </aside>
</template>

<style lang="scss">
.MenuWrapper {
  width: 304px;
  height: 100%;

  &__icon {
    height: 24px;
  }

  &__logoAndAssistant {
    border-bottom: 1px solid var(--gray_20);
    width: 100%;

    &Wrapper {
      display: flex;
      align-items: center;
      padding: 16px 24px;
      gap: 8px;
      cursor: pointer;
    }
  }

  &__mainItemsWrapper {
    padding: 12px;
    border-bottom: 1px solid var(--gray_20);
  }
}
</style>
