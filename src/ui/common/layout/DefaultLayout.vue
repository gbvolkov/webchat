<script lang="ts" setup>
import { Menu } from '@/ui/common/layout/menu'
import { MobileMenu } from '@/ui/common/layout/menu/mobile-menu'
import { useShowMenu } from '@/ui/common/layout/menu/use-show-menu'

const { isShowMenu, handleToggleMenu } = useShowMenu()
</script>

<template>
  <div class="Layout">
    <div class="Layout__main">
      <div
          class="Layout__overlay"
          :class="{ 'Layout__overlay_active': isShowMenu }"
          @click="handleToggleMenu"
      />

      <Menu
          class="Layout__sidebar"
          :class="{ 'Layout__sidebar_active': isShowMenu }"
      />

      <div class="Layout__middleSection">
        <MobileMenu
            class="Layout__mobileMenu"
            :whenBurgerClick="handleToggleMenu"
        />
        <slot />
      </div>
    </div>
  </div>
</template>

<style lang="css" scoped>
.Layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.Layout__main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.Layout__mobileMenu {
  display: none;
}

.Layout__sidebar {
  width: 304px;
  overflow-y: auto;
  flex-shrink: 0;
  border-right: 1px solid var(--gray_20);
  background: white;
  transition: transform 0.3s ease;
}

.Layout__middleSection {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  overflow-y: auto;
  background-color: var(--gray_white);
}

.Layout__overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
}

.Layout__overlay_active {
  display: block;
}

@media (max-width: 1280px) {
  .Layout__sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    width: 300px;
    z-index: 1000;
    transform: translateX(-100%);
  }

  .Layout__sidebar_active {
    transform: translateX(0);
  }

  .Layout__mobileMenu {
    display: flex;
    position: relative;
    z-index: 998;
  }

  :global(body.menu-open) {
    overflow: hidden;
  }
}
</style>
