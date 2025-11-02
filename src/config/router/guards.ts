import type { Pinia } from 'pinia'
import type { Router } from 'vue-router'
import { useAuthStore } from '@/store/auth-store'
import { Routes } from './routes'

export const registerAuthGuards = (router: Router, pinia: Pinia) => {
  router.beforeEach(async (to, from, next) => {
    const authStore = useAuthStore(pinia)
    await authStore.ensureInitialized()

    const requiresAuth = to.meta.requiresAuth !== false
    let hasActiveSession = authStore.hasSession

    console.log(
      '[auth-guard] navigation',
      `${from.fullPath || '/'} -> ${to.fullPath || '/'}`,
      `requiresAuth=${requiresAuth}`,
      `isInitialized=${authStore.isInitialized}`,
      `isAuthenticated=${authStore.isAuthenticated}`,
      `sessionStatus=${authStore.sessionStatus}`,
      `hasAccessToken=${Boolean(authStore.accessToken)}`,
      `hasRefreshToken=${authStore.hasRefreshToken}`,
      `hasActiveSession=${hasActiveSession}`,
      `hasSession=${authStore.hasSession}`,
    )

    if (requiresAuth && !hasActiveSession) {
      if (authStore.hasRefreshToken) {
        try {
          await authStore.ensureValidAccessToken()
          hasActiveSession = authStore.hasSession
        } catch (error) {
          console.warn('[auth-guard] failed to ensure valid access token during navigation', error)
        }
      }
      if (!hasActiveSession && from.name === Routes.Login && authStore.hasSession) {
        console.log('[auth-guard] allowing navigation with freshly issued token')
        hasActiveSession = true
      }
    }

    if (requiresAuth && !hasActiveSession) {
      const redirect = to.fullPath && to.fullPath !== '/login' ? { redirect: to.fullPath } : undefined
      return next({
        name: Routes.Login,
        ...(redirect ? { query: redirect } : {}),
      })
    }

    if (to.name === Routes.Login && hasActiveSession) {
      return next({ name: Routes.Chat })
    }

    return next()
  })

  router.afterEach((to, from) => {
    console.log('[auth-guard] resolved', {
      from: from.fullPath,
      to: to.fullPath,
    })
  })
}
