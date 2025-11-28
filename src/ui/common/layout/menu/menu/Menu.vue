<script lang="ts" setup>
import { ref, watch, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import folder from '@/assets/icons/menu/folder.svg'
import figures from '@/assets/icons/menu/figures.svg'
import dialog from '@/assets/icons/menu/dialog.svg'
import search from '@/assets/icons/menu/search.svg'
import logo from '@/assets/icons/menu/logo.svg'
import assistant from '@/assets/icons/menu/assistant.svg'
import MenuItem from './MenuItem.vue'
import { Routes } from '@/config/router/routes'
import { ThreadsWrapper } from '@/ui/common/layout/threads-wrapper'
import { EventKeys } from '@/ui/common/layout/menu/types'
import { useAuthStore } from '@/store/auth-store'
import { ThreadsApi } from '@/domain/threads/api'
import { LanguageSwitcher } from '@/ui/common/language-switcher'
import type { ThreadExportFormat } from '@/domain/threads/types'
import { downloadBlobAsFile } from '@/utils/download-file'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { t, locale } = useI18n()

const selectedKey = ref<string>(route.name as string)
const threadsWrapperRef = ref<InstanceType<typeof ThreadsWrapper> | null>(null)

const selectedThreadId = computed((): string => {
  return selectedKey.value?.includes(Routes.ChatDetail)
    ? (route.params.id as string) || ''
    : ''
})

watch(
  () => route.name,
  (newRouteName) => {
    if (newRouteName) {
      selectedKey.value = newRouteName as string
    }
  },
  { immediate: true, deep: true },
)

interface IMenuItem {
  label: string
  key: EventKeys
  icon: string
  type?: 'group'
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

const HIDDEN_MENU_KEYS = new Set<EventKeys>([EventKeys.ChatHistory, EventKeys.ChatLibrary])

const menuItems = computed<IMenuItem[]>(() => {
  void locale.value

  return [
    {
      key: EventKeys.NewChat,
      icon: CHAT_ICONS[EventKeys.NewChat],
      label: t('menu.items.newChat'),
    },
    {
      key: EventKeys.ChatSearch,
      icon: CHAT_ICONS[EventKeys.ChatSearch],
      label: t('menu.items.chatSearch'),
    },
    {
      key: EventKeys.ChatHistory,
      icon: CHAT_ICONS[EventKeys.ChatHistory],
      label: t('menu.items.chatHistory'),
    },
    {
      key: EventKeys.ChatLibrary,
      icon: CHAT_ICONS[EventKeys.ChatLibrary],
      label: t('menu.items.chatLibrary'),
    },
  ].filter((item) => !HIDDEN_MENU_KEYS.has(item.key))
})

const createNewThread = async () => {
  if (!authStore.hasSession) {
    message.warning(t('menu.needsAuth'))
    return
  }
  try {
    const { data } = await ThreadsApi.createThread()
    await threadsWrapperRef.value?.refresh()
    selectedKey.value = Routes.ChatDetail
    router.push({
      name: Routes.ChatDetail,
      params: { id: data.id },
    })
  } catch (error) {
    message.error(t('menu.errors.create'))
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

const handleExportThread = async (id: string, format: ThreadExportFormat) => {
  const extension = format === 'pdf' ? 'pdf' : format === 'docx' ? 'docx' : 'md'
  const filename = `thread-${id}.${extension}`
  try {
    const { data } = await ThreadsApi.exportThread(id, format)
    const blob = data instanceof Blob ? data : new Blob([data])
    downloadBlobAsFile(blob, filename)
    message.success(t('threads.notifications.exportSuccess'))
  } catch (error) {
    message.error(t('threads.notifications.exportFailed'))
    console.error('Failed to export thread', error)
  }
}

const handleDeleteThread = (id: string) => {
  Modal.confirm({
    title: t('common.confirmations.deleteChat.title'),
    content: t('common.confirmations.deleteChat.description'),
    okText: t('common.confirmations.deleteChat.confirm'),
    cancelText: t('common.confirmations.deleteChat.cancel'),
    okType: 'danger',
    async onOk() {
      try {
        await ThreadsApi.deleteThread(id)
        message.success(t('menu.success.delete'))
        await threadsWrapperRef.value?.refresh()

        if (selectedKey.value.startsWith(`${Routes.ChatDetail}/`)) {
          router.push({ name: Routes.Chat })
        }
        window.dispatchEvent(new CustomEvent('threads:refresh'))
      } catch (error) {
        message.error(t('menu.errors.delete'))
        console.error('Failed to delete thread', error)
      }
    },
  })
}

const refreshThreads = () => threadsWrapperRef.value?.refresh()
const handleLogout = async () => {
  await authStore.logout()
}

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
          v-for="({ label, key, icon }, index) in menuItems"
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
        :whenExportThread="handleExportThread"
    />

    <div class="MenuWrapper__language">
      <LanguageSwitcher />
    </div>

    <button
        class="MenuWrapper__logout"
        type="button"
        @click="handleLogout"
    >
      {{ $t('menu.signOut') }}
    </button>
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

  &__language {
    padding: 16px 12px 0 12px;
  }

  &__logout {
    width: calc(100% - 24px);
    margin: 16px 12px;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid var(--gray_20);
    background: white;
    color: var(--gray_80);
    font-family: var(--main_font);
    font-size: 14px;
    cursor: pointer;
    transition: background-color 0.2s ease, color 0.2s ease;

    &:hover {
      background-color: var(--gray_10);
      color: var(--gray_100);
    }

    &:active {
      background-color: var(--gray_20);
    }
  }
}
</style>
