<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { DefaultLayout } from '@/ui/common/layout'
import { useAuthStore } from '@/store/auth-store'

const route = useRoute()
const authStore = useAuthStore()
const { t } = useI18n()

const useDefaultLayout = computed(() => route.meta?.layout !== 'blank')
const requiresAuth = computed(() => route.meta?.requiresAuth !== false)

const isCheckingSession = computed(() => requiresAuth.value && !authStore.isInitialized)

const statusMessage = computed(() => {
  if (isCheckingSession.value) {
    return authStore.hasRefreshToken
      ? t('app.status.checkingSession')
      : t('app.status.preparingSignIn')
  }
  if (authStore.isAuthenticated) {
    const name = authStore.displayName || authStore.userId
    return t('app.status.welcomeBack', { name })
  }
  return ''
})

console.debug('[app] route update', {
  path: route.fullPath,
  requiresAuth: requiresAuth.value,
  isCheckingSession: isCheckingSession.value,
  isInitialized: authStore.isInitialized,
  isAuthenticated: authStore.isAuthenticated,
})
</script>

<template>
  <DefaultLayout v-if="useDefaultLayout">
    <div v-if="isCheckingSession" class="App__loading">
      <span class="App__spinner" aria-hidden="true" />
      <span>{{ statusMessage }}</span>
    </div>
    <RouterView v-else />
  </DefaultLayout>
  <div v-else class="BlankLayout">
    <div v-if="isCheckingSession" class="App__loading">
      <span class="App__spinner" aria-hidden="true" />
      <span>{{ statusMessage }}</span>
    </div>
    <RouterView v-else />
  </div>
</template>

<style scoped>
.BlankLayout {
  min-height: 100vh;
}

.App__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px;
  color: var(--gray_80, #4b5563);
  font-family: var(--main_font, 'Inter', sans-serif);
  font-size: 16px;
}

.App__spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(59, 130, 246, 0.35);
  border-left-color: rgba(59, 130, 246, 0.9);
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
