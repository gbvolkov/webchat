<script lang="ts" setup>
import burger from '@/assets/icons/menu/burger.svg'
import { LanguageSwitcher } from '@/ui/common/language-switcher'

interface Props {
  whenBurgerClick: () => void
}

const props = defineProps<Props>()
</script>

<template>
  <div class="MobileMenu">
    <button
        class="MobileMenu__burger"
        type="button"
        @click="props.whenBurgerClick"
    >
      <span class="visually-hidden"></span>
      <img :src="burger" alt="burger">
    </button>

    <LanguageSwitcher class="MobileMenu__language" />
  </div>
</template>

<style lang="scss" scoped>
.MobileMenu {
  height: 60px;
  border-bottom: 1px solid var(--gray_20);
  justify-content: space-between;
  display: flex;
  align-items: center;
  padding: 14px 20px;
  width: 100%;
  gap: 16px;
}

.MobileMenu__burger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--gray_20);
  background-color: white;
  cursor: pointer;
}

.MobileMenu__language {
  flex: 1;
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
