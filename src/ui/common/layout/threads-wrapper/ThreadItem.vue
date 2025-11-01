<script lang="ts" setup>
import { computed } from 'vue'
import type { ThreadSummary } from '@/domain/threads/types'
import TextView from '@/ui/common/text-view/TextView.vue'

interface Props {
  threadItem: ThreadSummary
  isSelected: boolean
  whenClickThreadItem: () => void
  whenDeleteThread?: (id: string) => Promise<void> | void
}

const props = defineProps<Props>()

const title = computed(() => props.threadItem.title?.trim() || 'Новый чат')
const subtitle = computed(() => {
  if (props.threadItem.summary?.trim()) return props.threadItem.summary
  const topic = props.threadItem.metadata?.['topic']
  if (typeof topic === 'string' && topic.trim().length > 0) return topic
  return `Тред ${props.threadItem.id.slice(0, 8)}`
})
</script>

<template>
  <div
      :class="[
      'ThreadItem',
      props.isSelected && 'ThreadItem_selected'
      ]"
  >
    <button
        v-if="props.whenDeleteThread"
        class="ThreadItem__delete"
        type="button"
        title="Удалить чат"
        @click.stop="props.whenDeleteThread?.(props.threadItem.id)"
    >
      ×
    </button>
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
  </div>
</template>
<style lang="scss">
.ThreadItem {
  text-overflow: ellipsis;
  position: relative;
  cursor: pointer;
  padding: 8px 32px 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: relative;


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

.ThreadItem__delete {
  position: absolute;
  top: 6px;
  right: 6px;
  border: none;
  background: transparent;
  color: var(--gray_50);
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
}

.ThreadItem__delete:hover {
  color: var(--error_50);
}
</style>
