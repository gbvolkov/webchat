<script setup lang="tsx">
import { noop } from '@/utils/noop'
import { ref } from 'vue'
import { HistoryCard } from '@/ui/common/history/card'
import {Props} from '@/ui/common/history/card/types'

const currentPage = ref()

const total = ref(500)

const pageSize = ref(20)

const data = ref<Props[]>([
    {
      tagType: 'purple',
      tagLabel: 'string',
      text: 'text',
      date: '22.03.2025',
      whenClickExport: noop,
      whenClickDelete: noop
    },
      {
        tagType: 'orange',
        tagLabel: 'string',
        text: 'text',
        date: '22.03.2025',
        whenClickExport: noop,
        whenClickDelete: noop
      },
      {
        tagType: 'blue',
        tagLabel: 'string',
        text: 'text',
        date: '22.03.2025',
        whenClickExport: noop,
        whenClickDelete: noop
      },
      {
        tagType: 'pink',
        tagLabel: 'string',
        text: 'text',
        date: '22.03.2025',
        whenClickExport: noop,
        whenClickDelete: noop
      },
      {
        tagType: 'blue',
        tagLabel: 'string',
        text: 'text',
        date: '22.03.2025',
        whenClickExport: noop,
        whenClickDelete: noop
      },
      {
        tagType: 'purple',
        tagLabel: 'string',
        text: 'text',
        date: '22.03.2025',
        whenClickExport: noop,
        whenClickDelete: noop
      }
]
)

</script>

<template>
<div class="AllTabsContentWrapper">
  <HistoryCard
      v-for="({ tagType, tagLabel, text, date, whenClickExport, whenClickDelete  }, i) in data"
      :key="i"
      :tagType="tagType"
      :tagLabel="tagLabel"
      :text="text"
      :date="date"
      :whenClickExport="whenClickExport"
      :whenClickDelete="whenClickDelete"
  />
</div>
  <a-pagination
      v-model:current="currentPage"
      :total="total"
      :page-size="pageSize"
      :show-size-changer="false"
      class="custom-pagination"
  />

</template>
<style lang="scss" scoped>
.AllTabsContentWrapper {
  display: grid;
  width: 100%;
  grid-template-columns: 1fr 1fr;
  grid-gap: 8px;
  margin-bottom: 48px;
}

@media (max-width: 767px) {
  .AllTabsContentWrapper {
    display: flex;
    flex-direction: column;
    gap: 8px
  }
}

.custom-pagination {
  --letter_color: var(--gray_100);
}

.custom-pagination :deep(.ant-pagination-item) {
  background: var(--gray_20) !important;
}

.custom-pagination :deep(.ant-pagination-item a) {
  color: var(--letter_color) !important;
}

.custom-pagination :deep(.ant-pagination-item.ant-pagination-item-active) {
  background: var(--brand_50) !important;
  border-color: var(--brand_50) !important;
}

.custom-pagination :deep(.ant-pagination-item.ant-pagination-item-active a) {
  color: var(--gray_white) !important;
}

/* Кнопки со стрелками - прозрачный фон */
.custom-pagination :deep(.ant-pagination-prev .ant-pagination-item-link),
.custom-pagination :deep(.ant-pagination-next .ant-pagination-item-link) {
  color: var(--letter_color) !important;
  background: transparent !important;
}

.custom-pagination :deep(.ant-pagination-prev.ant-pagination-disabled .ant-pagination-item-link),
.custom-pagination :deep(.ant-pagination-next.ant-pagination-disabled .ant-pagination-item-link) {
  color: var(--gray_60) !important;
  background: initial !important;
  background: initial !important;
  border-color: 1px solid white !important;
}

.custom-pagination :deep(.ant-pagination-jump-prev .ant-pagination-item-container .ant-pagination-item-ellipsis),
.custom-pagination :deep(.ant-pagination-jump-next .ant-pagination-item-container .ant-pagination-item-ellipsis) {
  color: var(--letter_color) !important;
}

/* Скрываем селектор количества элементов */
.custom-pagination :deep(.ant-pagination-options) {
  display: none !important;
}
</style>
