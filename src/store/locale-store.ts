import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { DEFAULT_LOCALE, SUPPORTED_LOCALES, type SupportedLocale, i18n } from '@/config/i18n'

const STORAGE_KEY = 'gwp-chat-locale'

const isBrowser = typeof window !== 'undefined'

function readStoredLocale(): SupportedLocale {
  if (!isBrowser) {
    return DEFAULT_LOCALE
  }

  const stored = window.localStorage.getItem(STORAGE_KEY) as SupportedLocale | null

  if (stored && SUPPORTED_LOCALES.includes(stored)) {
    return stored
  }

  return DEFAULT_LOCALE
}

function persistLocale(locale: SupportedLocale) {
  if (!isBrowser) {
    return
  }

  window.localStorage.setItem(STORAGE_KEY, locale)
}

export const useLocaleStore = defineStore('locale', () => {
  const locale = ref<SupportedLocale>(readStoredLocale())

  const setLocale = (value: SupportedLocale) => {
    if (!SUPPORTED_LOCALES.includes(value)) {
      return
    }

    locale.value = value
  }

  watch(
    locale,
    (value) => {
      i18n.global.locale.value = value
      persistLocale(value)
    },
    { immediate: true },
  )

  return {
    locale,
    availableLocales: SUPPORTED_LOCALES,
    setLocale,
  }
})
