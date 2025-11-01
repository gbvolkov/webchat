<script lang="ts" setup>
import {computed} from 'vue'
import {EventKeys} from "@/ui/common/layout/menu/types";

interface Props {
  whenClick: (event: Event) => void
  label: string
  leftContentIcon: string
  selectedRoute: string
  eventKey: EventKeys | string
}

const props = defineProps<Props>()

const isSelected = computed(() => props.selectedRoute === props.eventKey)
</script>

<template>
  <button
      :class="['MenuItem', { 'MenuItem__selected': isSelected }]"
      @click="props.whenClick"
  >
    <div class="MenuItem__left">
      <img
          :src="leftContentIcon"
          alt="icon"
          :class="{'MenuItem__icon': isSelected,
           }"
      />
    </div>

    <div
        :class="['MenuItem__label', { 'MenuItem__selected': isSelected }]"
    >
      {{ props.label }}
    </div>

    <div class="MenuItem__right">
      <slot name="rightContent"/>
    </div>
  </button>
</template>

<style lang="scss" scoped>
.MenuItem {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  text-overflow: ellipsis;
  height: 36px;
  padding: 8px 12px;
  width: 100%;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: var(--gray_20);
  }

  &__selected {
    color: var(--brand_50);
  }

  &__icon {
    color: var(--brand_50);
    filter: brightness(0) saturate(100%) invert(33%) sepia(98%) saturate(1232%) hue-rotate(194deg) brightness(93%) contrast(101%);
  }

  &__left,
  &__right {
    display: flex;
    align-items: center;
  }

  &__label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: inherit; /* Наследуем цвет от родителя */
  }
}
</style>