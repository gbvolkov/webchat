import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { Pinia } from 'pinia'
import type { Router } from 'vue-router'
import { useAuthStore } from '@/store/auth-store'
import { Routes } from '@/config/router/routes'
import { API_BASE_URL } from '@/config/api'

export { API_BASE_URL } from '@/config/api'

export const DefaultAPIInstance = axios.create()

DefaultAPIInstance.defaults.baseURL = API_BASE_URL

export const SKIP_AUTH_REFRESH_HEADER = 'X-Skip-Auth-Refresh'

type RetriableConfig = InternalAxiosRequestConfig & {
  __isRetry?: boolean
}

type QueueEntry = {
  resolve: (value: unknown) => void
  reject: (reason?: unknown) => void
  config: RetriableConfig
}

let interceptorsRegistered = false

export const setupApiInterceptors = (pinia: Pinia, router: Router) => {
  if (interceptorsRegistered) return
  interceptorsRegistered = true

  const authStore = useAuthStore(pinia)

  let isRefreshing = false
  const queue: QueueEntry[] = []

const setAuthorizationHeader = (headers: InternalAxiosRequestConfig['headers'], token: string) => {
  if (!headers) return

  if (typeof (headers as any).set === 'function') {
    const axiosHeaders = headers as unknown as {
      set: (key: string, value: string) => void
    }
    axiosHeaders.set('Authorization', `Bearer ${token}`)
    return
  }

  const plain = headers as Record<string, unknown>
  plain.Authorization = `Bearer ${token}`
}

const hasSkipAuthRefreshHeader = (headers: InternalAxiosRequestConfig['headers']): boolean => {
  if (!headers) return false
  const headerKey = SKIP_AUTH_REFRESH_HEADER.toLowerCase()
  const anyHeaders = headers as any
  if (typeof anyHeaders.get === 'function') {
    const value = anyHeaders.get(SKIP_AUTH_REFRESH_HEADER) ?? anyHeaders.get(headerKey)
    return value !== undefined && value !== null && String(value).toLowerCase() !== 'false'
  }
  const directValue = anyHeaders[SKIP_AUTH_REFRESH_HEADER] ?? anyHeaders[headerKey]
  return directValue !== undefined && directValue !== null && String(directValue).toLowerCase() !== 'false'
}

const getRequestPath = (url?: string | null): string => {
  if (!url) return ''
  try {
    return new URL(url, API_BASE_URL).pathname ?? ''
  } catch {
    try {
      return new URL(url).pathname ?? ''
    } catch {
      return url.startsWith('/') ? url : `/${url}`
    }
  }
}

const isPublicAuthEndpoint = (path: string): boolean => {
  if (!path) return false
  const normalized = path.endsWith('/') && path.length > 1 ? path.slice(0, -1) : path
  return ['/auth/login', '/auth/register', '/auth/refresh'].some((endpoint) =>
    normalized === endpoint || normalized.startsWith(`${endpoint}/`),
  )
}

  const enqueueRequest = (config: RetriableConfig) =>
    new Promise((resolve, reject) => {
      queue.push({ resolve, reject, config })
    })

  const processQueue = (error: unknown, token: string | null) => {
    while (queue.length > 0) {
      const { resolve, reject, config } = queue.shift()!
      if (error) {
        reject(error)
        continue
      }
      config.headers = config.headers ?? {}
      if (token) {
        setAuthorizationHeader(config.headers, token)
      }
      config.__isRetry = true
      resolve(DefaultAPIInstance(config))
    }
  }

  DefaultAPIInstance.interceptors.request.use(
    async (config) => {
      config.headers = config.headers ?? {}

      const path = getRequestPath(config.url)
      const skipAuth = isPublicAuthEndpoint(path)
      const skipRefresh = hasSkipAuthRefreshHeader(config.headers)

      if (!skipAuth) {
        try {
          await authStore.ensureInitialized()
        } catch (error) {
          console.warn('[axios] initialization before request failed', {
            path,
            error,
          })
        }

        const hasSession = authStore.isAuthenticated

        if (hasSession) {
          let token: string | null = null

          if (skipRefresh) {
            token = authStore.accessToken
          } else {
            try {
              token = await authStore.ensureValidAccessToken()
            } catch (error) {
              console.warn('[axios] failed to obtain valid access token', {
                path,
                error,
              })
              token = authStore.accessToken
            }
          }

          if (!token) {
            token = authStore.accessToken
          }

          if (token) {
            setAuthorizationHeader(config.headers, token)
          }
        }
      }

      let authHeader: string | undefined
      const headersAny = config.headers as any
      if (headersAny) {
        if (typeof headersAny.get === 'function') {
          authHeader = headersAny.get('Authorization') ?? headersAny.get('authorization')
        } else {
          authHeader = headersAny.Authorization ?? headersAny.authorization
        }
      }
      console.debug('[axios] request', {
        method: config.method,
        url: config.url,
        authHeader,
        skipAuth,
        skipRefresh,
        defaultAuth: DefaultAPIInstance.defaults.headers.common?.Authorization,
      })
      return config
    },
    (error) => Promise.reject(error),
  )

  DefaultAPIInstance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const response = error.response
      const originalConfig = error.config as RetriableConfig | undefined
      const headers = (originalConfig?.headers as Record<string, unknown>) ?? {}
      const skipRefresh =
        Boolean(headers[SKIP_AUTH_REFRESH_HEADER]) || Boolean(headers[SKIP_AUTH_REFRESH_HEADER.toLowerCase()])

      if (!response || response.status !== 401 || !originalConfig || skipRefresh) {
        return Promise.reject(error)
      }

      if (originalConfig.__isRetry) {
        return Promise.reject(error)
      }

      if (!authStore.hasRefreshToken) {
        authStore.forceLogout()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return enqueueRequest(originalConfig)
      }

      originalConfig.__isRetry = true
      isRefreshing = true

      try {
        const newToken = await authStore.refreshTokens()
        processQueue(null, newToken)

        originalConfig.headers = originalConfig.headers ?? {}
        setAuthorizationHeader(originalConfig.headers, newToken)
        return DefaultAPIInstance(originalConfig)
      } catch (refreshError) {
        processQueue(refreshError, null)
        authStore.forceLogout()

        const currentRoute = router.currentRoute.value
        if (currentRoute.name !== Routes.Login) {
          const redirect =
            currentRoute.fullPath && currentRoute.fullPath !== '/login' ? { redirect: currentRoute.fullPath } : undefined
          router.push({
            name: Routes.Login,
            ...(redirect ? { query: redirect } : {}),
          })
        }

        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    },
  )
}
