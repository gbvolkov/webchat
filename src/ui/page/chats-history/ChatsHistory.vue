<script setup lang="tsx">
import { computed, ref } from 'vue'
import lupa from '@/assets/icons/search/lupa.svg'
import TextView from '@/ui/common/text-view/TextView.vue'
import { Tabs } from '@/ui/common/history/tabs'
import { AllTabContent } from '@/ui/common/history/all-tab-content'
import { ChatHistoryTab } from '@/ui/common/history/tabs'
import { ScreenSize, useScreenSize } from '@/composables/useScreenSize'
import { ITextViewVariant } from '@/ui/common/text-view/types'

const { screenSize } = useScreenSize()

const selectedTab = ref<ChatHistoryTab>(ChatHistoryTab.All)

const search = ref('')

const headerVariant = computed((): ITextViewVariant => {
  switch (screenSize.value) {
    case ScreenSize.MOBILE:
      return 'roboto_28_bold'
    case ScreenSize.TABLET:
    case ScreenSize.DESKTOP_SMALL:
    case ScreenSize.DESKTOP_XL:
      return 'roboto_32_bold'
    case ScreenSize.DESKTOP_LARGE:
    default:
      return 'roboto_36_bold'

  }
})

const whenTabSelect = (tab: ChatHistoryTab) => selectedTab.value = tab

const renderTabContent = computed(() => {
  switch (selectedTab.value) {
    case ChatHistoryTab.All:
      return (
          <AllTabContent class="HistoryPage__tabsContent" />
      )

    default: return <div class="HistoryPage__tabsContent">В будущем, здесь будет контент...</div>
  }
})
</script>

<template>
  <div class="HistoryPage">
    <div class="HistoryPage__wrapper">
      <TextView
          :variant="headerVariant"
          class="HistoryPage__header"
      >
        История чатов
      </TextView>

      <TextView
          variant="roboto_14_regular"
          color="gray_60"
          class="HistoryPage__label"
      >
        Text description in 2 lines. Text description in 2 lines. Text description in 2 lines
        Text description in 2 linesText description in 2 lines
      </TextView>

      <a-input
          v-model:value="search"
          placeholder="Поиск"
          class="HistoryPage__input"
          size="large"
      >
        <template #suffix>
         <img :src="lupa" alt="Лупа" />
        </template>
      </a-input>
      <Tabs
          :selectedTab="selectedTab"
          :whenTabSelect="whenTabSelect"
          class="HistoryPage__tabs"
        />

      <component :is="renderTabContent" />
    </div>

  </div>
</template>
<style lang="css">
.HistoryPage {
  min-height: 100vh;
  background-color: var(--gray_0);
}

.HistoryPage__wrapper {
  display: grid;
  place-items: center;
  margin: 0 auto;
  max-width: 808px;
}

.HistoryPage__tabsContent {
  margin-bottom: 48px;
}

.HistoryPage__label {
  text-align: center;
  margin-bottom: 32px;
}

.HistoryPage__header {
  margin-bottom: 16px;
}

.HistoryPage__tabs {
  width: 100%;
  margin-bottom: 24px;
}

.HistoryPage__input {
  margin-bottom: 90px;
}

@media (max-width: 767px) {
  .HistoryPage {
    padding: 48px 24px;
  }

  .HistoryPage__header {
    margin-top: 48px;
    margin-bottom: 12px;
  }
}

@media (min-width: 768px) and (max-width: 1023px) {
  .HistoryPage {
    padding: 0 40px;
  }

  .HistoryPage__header {
    margin-top: 40px;
  }
}

@media (min-width: 1024px) and (max-width: 1279px) {
  .HistoryPage {
    padding: 0 84px;
  }

  .HistoryPage__header {
    margin-top: 56px;
  }
}

/* Desktop Large */
@media (min-width: 1280px) and (max-width: 1920px) {
  .HistoryPage {
    padding: 0 164px;
  }

  .HistoryPage__header {
    margin-top: 60px;
  }
}

@media (min-width: 1920px) {
  .HistoryPage__header {
    margin-top: 80px;
  }

}
</style>
