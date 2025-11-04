<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLocaleStore } from '@/store/locale-store'
import type { SupportedLocale } from '@/config/i18n'

const { t, locale } = useI18n()
const localeStore = useLocaleStore()

const localeModel = computed({
  get: () => localeStore.locale,
  set: (nextLocale: SupportedLocale) => {
    localeStore.setLocale(nextLocale)
  },
})

const optionKeyMap: Record<SupportedLocale, string> = {
  en: 'language.english',
  ru: 'language.russian',
}

const options = computed(() => {
  // access locale to ensure reactivity when language changes
  void locale.value

  return localeStore.availableLocales.map((availableLocale) => ({
    value: availableLocale,
    label: t(optionKeyMap[availableLocale]),
  }))
})
</script>

<template>
  <div class="LanguageSwitcher">
    <span class="LanguageSwitcher__labelText">
      {{ $t('language.label') }}
    </span>
    <div class="LanguageSwitcher__selector">
      <select
          v-model="localeModel"
          class="LanguageSwitcher__select"
      >
        <option
            v-for="option in options"
            :key="option.value"
            :value="option.value"
        >
          {{ option.label }}
        </option>
      </select>
    </div>
  </div>
</template>

<style scoped>
.LanguageSwitcher {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-family: var(--main_font, 'Inter', sans-serif);
  color: var(--gray_80, #4b5563);
}

.LanguageSwitcher__selector {
  position: relative;
}

.LanguageSwitcher__labelText {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.LanguageSwitcher__select {
  width: 100%;
  padding: 8px 32px 8px 12px;
  border: 1px solid var(--gray_20, #e5e7eb);
  border-radius: 8px;
  background-color: white;
  font: inherit;
  color: inherit;
  appearance: none;
  cursor: pointer;
}

.LanguageSwitcher__select:focus {
  outline: 2px solid var(--primary_40, #3b82f6);
  outline-offset: 1px;
}
</style>
