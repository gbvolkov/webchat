import { defineStore } from 'pinia'
import { ref } from 'vue'
import { AuthApi, type LoginRequest, type TokenResponse, type UserProfile } from '@/domain/auth/api'
import { DefaultAPIInstance } from '@/api/instance'

const ACCESS_TOKEN_KEY = 'gwp.auth.accessToken'
const REFRESH_TOKEN_KEY = 'gwp.auth.refreshToken'
const ACCESS_TOKEN_EXPIRES_AT_KEY = 'gwp.auth.accessTokenExpiresAt'
const REFRESH_TOKEN_EXPIRES_AT_KEY = 'gwp.auth.refreshTokenExpiresAt'

const TOKEN_EXPIRY_BUFFER_MS = 5_000

const readNumber = (key: string): number | null => {
  const raw = window.localStorage.getItem(key)
  if (!raw) return null
  const parsed = Number.parseInt(raw, 10)
  return Number.isNaN(parsed) ? null : parsed
}

const writeNumber = (key: string, value: number | null) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    window.localStorage.setItem(key, String(value))
    return
  }
  window.localStorage.removeItem(key)
}

const emitEvent = (name: string, detail?: unknown) => {
  window.dispatchEvent(new CustomEvent(name, { detail }))
}

const serializeToken = (token: string | null) => (token ? token.trim() : null)

const applyAxiosDefaults = (token: string | null) => {
  if (token) {
    DefaultAPIInstance.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    delete DefaultAPIInstance.defaults.headers.common.Authorization
  }
}

interface DecodedTokenClaims {
  sub?: string | null
  username?: string | null
}

const decodeTokenClaims = (token: string | null): DecodedTokenClaims | null => {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    const payloadJson = window.atob(padded)
    const payload = JSON.parse(payloadJson) as DecodedTokenClaims
    return payload
  } catch {
    return null
  }
}

const decodeTokenSubject = (token: string | null): string | null => {
  const claims = decodeTokenClaims(token)
  const subject = claims?.sub
  return typeof subject === 'string' && subject.trim().length > 0 ? subject : null
}

const decodeTokenUsername = (token: string | null): string | null => {
  const claims = decodeTokenClaims(token)
  const username = claims?.username
  return typeof username === 'string' && username.trim().length > 0 ? username : null
}

export const useAuthStore = defineStore('auth', () => {
  const accessTokenRef = ref<string | null>(serializeToken(window.localStorage.getItem(ACCESS_TOKEN_KEY)))
  const refreshTokenRef = ref<string | null>(serializeToken(window.localStorage.getItem(REFRESH_TOKEN_KEY)))
  const accessTokenExpiresAt = ref<number | null>(readNumber(ACCESS_TOKEN_EXPIRES_AT_KEY))
  const refreshTokenExpiresAt = ref<number | null>(readNumber(REFRESH_TOKEN_EXPIRES_AT_KEY))

  const profile = ref<UserProfile | null>(null)

  applyAxiosDefaults(accessTokenRef.value)

  const isInitialized = ref(false)
  const isAuthenticating = ref(false)
  const sessionStatus = ref<'authenticated' | 'anonymous'>('anonymous')
  const hasStoredTokens = () =>
    Boolean(window.localStorage.getItem(ACCESS_TOKEN_KEY) || window.localStorage.getItem(REFRESH_TOKEN_KEY))

  let initializePromise: Promise<void> | null = null
  let refreshPromise: Promise<string> | null = null

  const hasValidAccessToken = () => {
    if (!accessTokenRef.value || !accessTokenExpiresAt.value) return false
    return accessTokenExpiresAt.value - Date.now() > TOKEN_EXPIRY_BUFFER_MS
  }

  const hasValidRefreshToken = () => {
    if (!refreshTokenRef.value || !refreshTokenExpiresAt.value) return false
    return refreshTokenExpiresAt.value - Date.now() > TOKEN_EXPIRY_BUFFER_MS
  }

  const updateAuthenticationState = (): boolean => {
    const authenticated = hasValidAccessToken() || hasValidRefreshToken()
    const nextStatus: 'authenticated' | 'anonymous' = authenticated ? 'authenticated' : 'anonymous'
    if (sessionStatus.value !== nextStatus) {
      console.log('[auth] session status change', {
        previous: sessionStatus.value,
        next: nextStatus,
        hasValidAccessToken: hasValidAccessToken(),
        hasValidRefreshToken: hasValidRefreshToken(),
      })
    }
    sessionStatus.value = nextStatus
    return authenticated
  }

  const persistTokens = (tokens: TokenResponse) => {
    console.debug('[auth] persist tokens', {
      accessExpiresIn: tokens.expires_in,
      refreshExpiresIn: tokens.refresh_expires_in,
    })
    accessTokenRef.value = serializeToken(tokens.access_token)
    refreshTokenRef.value = serializeToken(tokens.refresh_token)
    const accessExpiryMs = Math.max(tokens.expires_in * 1000 - TOKEN_EXPIRY_BUFFER_MS, TOKEN_EXPIRY_BUFFER_MS)
    const refreshExpiryMs = Math.max(tokens.refresh_expires_in * 1000 - TOKEN_EXPIRY_BUFFER_MS, TOKEN_EXPIRY_BUFFER_MS)
    accessTokenExpiresAt.value = Date.now() + accessExpiryMs
    refreshTokenExpiresAt.value = Date.now() + refreshExpiryMs

    if (accessTokenRef.value) {
      window.localStorage.setItem(ACCESS_TOKEN_KEY, accessTokenRef.value)
      applyAxiosDefaults(accessTokenRef.value)
    } else {
      window.localStorage.removeItem(ACCESS_TOKEN_KEY)
      applyAxiosDefaults(null)
    }

    if (refreshTokenRef.value) {
      window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshTokenRef.value)
    } else {
      window.localStorage.removeItem(REFRESH_TOKEN_KEY)
    }
    writeNumber(ACCESS_TOKEN_EXPIRES_AT_KEY, accessTokenExpiresAt.value)
    writeNumber(REFRESH_TOKEN_EXPIRES_AT_KEY, refreshTokenExpiresAt.value)
    updateAuthenticationState()
  }

  const clearPersistence = () => {
    console.debug('[auth] clear persistence')
    accessTokenRef.value = null
    refreshTokenRef.value = null
    accessTokenExpiresAt.value = null
    refreshTokenExpiresAt.value = null
    profile.value = null

    window.localStorage.removeItem(ACCESS_TOKEN_KEY)
    window.localStorage.removeItem(REFRESH_TOKEN_KEY)
    window.localStorage.removeItem(ACCESS_TOKEN_EXPIRES_AT_KEY)
    window.localStorage.removeItem(REFRESH_TOKEN_EXPIRES_AT_KEY)
    applyAxiosDefaults(null)
    updateAuthenticationState()
  }

  const fetchProfile = async () => {
    console.log('[auth] fetching profile')
    const token = accessTokenRef.value
    if (!token) {
      throw new Error('Cannot fetch profile without an access token')
    }
    const response = await AuthApi.me(token)
    console.log('[auth] profile fetched', response.data)
    profile.value = response.data
    console.log('[auth] profile stored', profile.value)
  }

  const ensureInitialized = async () => {
    console.debug('[auth] ensureInitialized (current state)', {
      isInitialized: isInitialized.value,
      hasRefreshToken: hasValidRefreshToken(),
      hasAccessToken: hasValidAccessToken(),
    })
    if (isInitialized.value) return
    if (!initializePromise) {
      initializePromise = (async () => {
        if (!hasValidRefreshToken()) {
          console.debug('[auth] no valid refresh token – clearing session')
          clearPersistence()
          return
        }

        try {
          if (!hasValidAccessToken()) {
            await refreshTokens()
          }
          if (!profile.value) {
            await fetchProfile()
          }
        } catch (error) {
          console.warn('[auth] failed to restore session', error)
          clearPersistence()
        }
      })()
        .finally(() => {
          console.debug('[auth] initialization complete', {
            isAuthenticated: !!profile.value,
          })
          isInitialized.value = true
          initializePromise = null
          updateAuthenticationState()
        })
    }

    await initializePromise
  }

  const refreshTokens = async (): Promise<string> => {
    if (!hasValidRefreshToken() || !refreshTokenRef.value) {
      throw new Error('Session expired')
    }

    console.debug('[auth] refreshTokens invoked', {
      queued: Boolean(refreshPromise),
    })

    if (refreshPromise) {
      return refreshPromise
    }

    refreshPromise = AuthApi.refresh(refreshTokenRef.value)
      .then((response) => {
        persistTokens(response.data)
        console.debug('[auth] refreshTokens succeeded')
        return response.data.access_token
      })
      .catch((error) => {
        console.warn('[auth] refreshTokens failed', error)
        clearPersistence()
        emitEvent('auth:logout')
        throw error
      })
      .finally(() => {
        refreshPromise = null
      })

    return refreshPromise
  }

  const ensureValidAccessToken = async (): Promise<string> => {
    await ensureInitialized()
    if (hasValidAccessToken() && accessTokenRef.value) {
      return accessTokenRef.value
    }

    const token = await refreshTokens()
    if (!token) {
      throw new Error('Unable to refresh session')
    }
    return token
  }

  const login = async (payload: LoginRequest) => {
    console.debug('[auth] login attempt', { username: payload.username })
    isAuthenticating.value = true
    try {
      const response = await AuthApi.login(payload)
      persistTokens(response.data)
      await fetchProfile()
      console.debug('[auth] login success', {
        userId: profile.value?.id,
        username: profile.value?.username,
      })
      emitEvent('auth:login')
      isInitialized.value = true
      updateAuthenticationState()
    } catch (error: unknown) {
      console.warn('[auth] login failed', error)
      clearPersistence()
      const message =
        (error as Error)?.message || 'Unable to sign in. Check your username and password and try again.'
      throw new Error(message)
    } finally {
      isAuthenticating.value = false
    }
  }

  const logout = async () => {
    console.debug('[auth] logout requested')
    try {
      if (accessTokenRef.value) {
        await AuthApi.logout()
      }
    } catch (error) {
      console.warn('Failed to logout cleanly', error)
    } finally {
      clearPersistence()
      isInitialized.value = true
      emitEvent('auth:logout')
      console.debug('[auth] logout complete')
    }
  }

  const forceLogout = () => {
    console.debug('[auth] force logout')
    clearPersistence()
    isInitialized.value = true
    emitEvent('auth:logout')
  }

  const authorizedFetch = async (
    input: RequestInfo | URL,
    init: RequestInit = {},
    options: { retry?: boolean } = {},
  ): Promise<Response> => {
    const token = await ensureValidAccessToken()
    const headers = new Headers(init.headers as HeadersInit | undefined)
    headers.set('Authorization', `Bearer ${token}`)

    const response = await fetch(input, {
      ...init,
      headers,
    })

    if (response.status === 401 && options.retry !== false) {
      if (!hasValidRefreshToken()) {
        forceLogout()
        return response
      }
      try {
        const newToken = await refreshTokens()
        const retryHeaders = new Headers(init.headers as HeadersInit | undefined)
        retryHeaders.set('Authorization', `Bearer ${newToken}`)
        return fetch(input, {
          ...init,
          headers: retryHeaders,
        })
      } catch (error) {
        forceLogout()
        throw error
      }
    }

    return response
  }

  updateAuthenticationState()

  return {
    profile,
    isInitialized,
    isAuthenticating,
    ensureInitialized,
    ensureValidAccessToken,
    refreshTokens,
    login,
    logout,
    forceLogout,
    authorizedFetch,
    get sessionStatus(): 'authenticated' | 'anonymous' {
      return sessionStatus.value
    },
    get accessToken(): string | null {
      return accessTokenRef.value
    },
    get refreshToken(): string | null {
      return refreshTokenRef.value
    },
    get hasRefreshToken(): boolean {
      return hasValidRefreshToken()
    },
    get isAuthenticated(): boolean {
      return sessionStatus.value === 'authenticated'
    },
    get hasSession(): boolean {
      if (sessionStatus.value === 'authenticated') return true
      if (hasValidAccessToken()) return true
      if (hasValidRefreshToken()) return true
      return hasStoredTokens()
    },
    get userId(): string {
      return profile.value?.id ?? decodeTokenSubject(accessTokenRef.value) ?? ''
    },
    get displayName(): string {
      const fullName = profile.value?.full_name?.trim()
      if (fullName) return fullName
      return profile.value?.username ?? decodeTokenUsername(accessTokenRef.value) ?? ''
    },
    get roles(): string[] {
      return profile.value?.roles ?? []
    },
    get allowedProducts(): string[] {
      return profile.value?.allowed_products ?? []
    },
    get allowedAgents(): string[] {
      return profile.value?.allowed_agents ?? []
    },
  }
})



