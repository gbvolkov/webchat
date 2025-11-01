<script lang="ts" setup>
import burger from '@/assets/icons/menu/burger.svg'
interface Props {
  whenBurgerClick: () => void
}

const props = defineProps<Props>()
</script>
<template>
  <div class="MobileMenu">
    <button @click="props.whenBurgerClick">
      <span class="visually-hidden"></span>
      <img :src="burger" alt="burger">
    </button>

    <a-button type="primary">
      Новый чат
    </a-button>

  </div>
</template>
<style lang="scss" scoped>
.MobileMenu {
  height: 60px;
  border-bottom: 1px solid var(--gray_20);
  justify-content: space-between;
  display: flex;
  align-items: center;
  padding: 14px 40px;
  width: 100%;
}

.visually-hidden {
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  height: 1px;
  overflow: hidden;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}

</style>