<script lang="ts" setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ThreadSummary, ThreadExportFormat } from '@/domain/threads/types'
import TextView from '@/ui/common/text-view/TextView.vue'

interface Props {
  threadItem: ThreadSummary
  isSelected: boolean
  whenClickThreadItem: () => void
  whenDeleteThread?: (id: string) => Promise<void> | void
  whenExportThread?: (id: string, format: ThreadExportFormat) => Promise<void> | void
}

const props = defineProps<Props>()
const { t, locale } = useI18n()

const isActionsOpen = ref(false)
const itemRef = ref<HTMLElement | null>(null)

const title = computed(() => {
  void locale.value
  return props.threadItem.title?.trim() || t('threads.untitled')
})

const subtitle = computed(() => {
  void locale.value

  if (props.threadItem.summary?.trim()) return props.threadItem.summary
  const topic = props.threadItem.metadata?.['topic']
  if (typeof topic === 'string' && topic.trim().length > 0) return topic
  return t('threads.fallbackTitle', { id: props.threadItem.id.slice(0, 8) })
})

const closeActions = () => {
  isActionsOpen.value = false
}

const toggleActions = () => {
  isActionsOpen.value = !isActionsOpen.value
}

const handleOutsideClick = (event: MouseEvent) => {
  if (!isActionsOpen.value) return
  const target = event.target as Node | null
  if (target && itemRef.value && !itemRef.value.contains(target)) {
    closeActions()
  }
}

const handleExport = (format: ThreadExportFormat) => {
  props.whenExportThread?.(props.threadItem.id, format)
  closeActions()
}

const handleDelete = () => {
  props.whenDeleteThread?.(props.threadItem.id)
  closeActions()
}

onMounted(() => {
  document.addEventListener('click', handleOutsideClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleOutsideClick)
})
</script>

<template>
  <div
      ref="itemRef"
      :class="[
      'ThreadItem',
      props.isSelected && 'ThreadItem_selected'
      ]"
  >
    <div
        class="ThreadItem__content"
        @click="props.whenClickThreadItem"
    >
      <TextView
          variant="roboto_13_regular"
          :class="[
              'ThreadItem__textView',
              props.isSelected && 'ThreadItem__textView_selected'
              ]"
      >
        {{ title }}
      </TextView>
      <TextView
          variant="roboto_13_regular"
          color="gray_60"
          class="ThreadItem__subtitle"
      >
        {{ subtitle }}
      </TextView>
    </div>

    <div class="ThreadItem__actions" @click.stop>
      <button
          class="ThreadItem__more"
          type="button"
          :title="$t('threads.actions.openMenu')"
          @click="toggleActions"
      >
        ...
      </button>
      <div
          v-if="isActionsOpen"
          class="ThreadItem__dropdown"
      >
        <button
            class="ThreadItem__dropdownItem"
            type="button"
            @click="handleExport('pdf')"
        >
          {{ $t('threads.actions.exportPdf') }}
        </button>
        <button
            class="ThreadItem__dropdownItem"
            type="button"
            @click="handleExport('markdown')"
        >
          {{ $t('threads.actions.exportMarkdown') }}
        </button>
        <button
            class="ThreadItem__dropdownItem"
            type="button"
            @click="handleExport('docx')"
        >
          {{ $t('threads.actions.exportDocx') }}
        </button>
        <button
            class="ThreadItem__dropdownItem ThreadItem__dropdownItem_danger"
            type="button"
            @click="handleDelete"
        >
          {{ $t('threads.actions.delete') }}
        </button>
      </div>
    </div>
  </div>
</template>
<style lang="scss">
.ThreadItem {
  text-overflow: ellipsis;
  position: relative;
  cursor: pointer;
  padding: 8px 12px 8px 12px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;


  &__textView {
    padding: 6px 12px;
    padding-bottom: 0;
  }

  &__textView_selected {
    color: var(--brand_50);
  }

  &__subtitle {
    padding: 0 12px 6px 12px;
    font-size: 12px;
  }

  &_selected::after {
    content: '';
    position: absolute;
    width: 4px;
    height: 32px;
    top: 8px;
    right: 0;
    background: url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNCIgaGVpZ2h0PSIzMiIgdmlld0JveD0iMCAwIDQgMzIiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0wIDRDMCAxLjc5MDg2IDEuNzkwODYgMCA0IDBWMzJDMS43OTA4NiAzMiAwIDMwLjIwOTEgMCAyOFY0WiIgZmlsbD0iIzAwNUFGRiIvPgo8L3N2Zz4K");
    border-radius: 4px 0px 0px 4px;
    z-index: 6;
    flex: none;
    order: 6;
    flex-grow: 0;
  }
}

.texView:hover {
  color: var(--brand_50);
}

.ThreadItem__content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
}

.ThreadItem__actions {
  position: relative;
  align-self: start;
}

.ThreadItem__more {
  border: none;
  background: transparent;
  color: var(--gray_60);
  cursor: pointer;
  font-size: 18px;
  padding: 4px 6px;
  line-height: 1;
  border-radius: 6px;
}

.ThreadItem__more:hover {
  background: var(--gray_10);
  color: var(--gray_100);
}

.ThreadItem__dropdown {
  position: absolute;
  right: 0;
  margin-top: 4px;
  background: var(--gray_0);
  border: 1px solid var(--gray_20);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 6px 0;
  min-width: 180px;
  z-index: 10;
}

.ThreadItem__dropdownItem {
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--gray_80);
  text-align: left;
  font-family: var(--main_font);
  font-size: 13px;
  cursor: pointer;
}

.ThreadItem__dropdownItem:hover {
  background: var(--gray_10);
  color: var(--gray_100);
}

.ThreadItem__dropdownItem_danger {
  color: var(--error_60);
}

.ThreadItem__dropdownItem_danger:hover {
  color: var(--error_70);
  background: rgba(244, 68, 68, 0.08);
}
</style>
