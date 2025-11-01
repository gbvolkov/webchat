<script lang="ts" setup>
import { computed } from 'vue'
import { Dropdown, Menu, MenuItem } from 'ant-design-vue'
import { Tag } from '@/ui/common/tag'
import dots from '@/assets/icons/history/dots.svg'
import exportImage from '@/assets/icons/history/export-image.svg'
import trash from '@/assets/icons/history/trash.svg'
import TextView from '@/ui/common/text-view/TextView.vue'
import { Props } from '@/ui/common/history/card/types'


const props = defineProps<Props>()

const menuItems = computed(() => [
  {
    key: 'export',
    label: 'Экспорт',
    icon: exportImage,
    onClick: props.whenClickExport,
    color: 'var(--gray_80)',
  },
  {
    key: 'delete',
    label: 'Удалить',
    icon: trash,
    onClick: props.whenClickDelete,
    color: 'var(--error_50)',
  }
])
</script>

<template>

  <div class="HistoryCard">
    <Tag
        :variant="props.tagType"
        class="HistoryCard__tag"
    >
      {{ props.tagLabel }}
    </Tag>

    <TextView
        variant="roboto_13_regular"
        class="HistoryCard__text"
    >
      {{ props.text }}
    </TextView>

    <div class="HistoryCard__footer">

      <TextView
          variant="roboto_13_regular"
          color="gray_60"
      >
        {{ props.date }}
      </TextView>

      <div>
        <Dropdown
            trigger="click"
            placement="bottomRight"
        >
          <button class="HistoryCard__contextMenu">
            <img :src="dots" alt="dots" />
          </button>

          <template #overlay>
            <Menu class="HistoryCard__menu">
              <MenuItem
                  v-for="({ label, onClick, icon, key, color }) in menuItems"
                  @click="onClick"
                  :key="key"
              >
                <div class="HistoryCard__menuItem">
                  <img :src="icon" alt="icon menu item" />

                  <div :style="{
                    color
                  }">
                    {{ label }}
                  </div>
                </div>

              </MenuItem>
            </Menu>
          </template>
        </Dropdown>
      </div>

    </div>
  </div>
</template>

<style lang="css" scoped>
.HistoryCard {
  padding: 13px 8px 4px 16px;
  border: 1px solid var(--gray_20);
  border-radius: 12px;
  background-color: var(--gray_white);
}

.HistoryCard__text {
  margin-bottom: 13px;
  padding-right: 8px;
}

.HistoryCard__tag {
  margin-bottom: 13px;
}

.HistoryCard__footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--gray_10);
  padding-top: 12px;
}

.HistoryCard__contextMenu {
  cursor: pointer;
}

.HistoryCard__menu {
  border: 1px solid var(--gray_30);
  border-radius: 6px;
  width: 220px;
}

.HistoryCard__menuItem {
  display: flex;
  align-items: center;
  gap: 14px;
}

</style>