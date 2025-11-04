<script lang="ts" setup>
import { ChatHistoryTab, CHAT_HISTORY_TABS } from './consts'
import { useI18n } from 'vue-i18n'
import { entries } from '@/utils/entries'

interface Props {
  selectedTab: ChatHistoryTab
  whenTabSelect: (tab: ChatHistoryTab) => void
}

const props = defineProps<Props>()
const { t } = useI18n()
</script>

<template>
  <div class="Tabs">
    <a-tag
        v-for="([key, tab]) in entries(CHAT_HISTORY_TABS)"
        class="Tabs__tab"
        :class="{ 'Tabs__tab_selected': props.selectedTab === key }"
        :key="key"
        @click="() => props.whenTabSelect(key )"
    >
      {{ t(tab) }}
    </a-tag>
  </div>
</template>

<style lang="scss" scoped>
.Tabs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.Tabs__tab {
  background-color: var(--gray_white);
  border: 1px solid var(--gray_10);
  color: var(--gray_60);
  cursor: pointer;
  padding: 4px 12px;
  border-radius: 6px;

  &_selected {
    background-color: var(--brand_50);
    border-color: var(--brand_50);
    color: var(--gray_white);
  }
}
</style>
