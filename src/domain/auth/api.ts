import axios, { type AxiosResponse } from 'axios'
import { API_BASE_URL } from '@/config/api'
import { DefaultAPIInstance, SKIP_AUTH_REFRESH_HEADER } from '@/api/instance'

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email?: string | null
  full_name?: string | null
  roles?: string[]
  allowed_products?: string[]
  allowed_agents?: string[]
  is_active?: boolean
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  refresh_expires_in: number
}

export interface UserProfile {
  id: string
  username: string
  email: string | null
  full_name?: string | null
  roles: string[]
  allowed_products: string[]
  allowed_agents: string[]
  token_version: number
  is_active: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
}

const AuthAPIInstance = axios.create({
  baseURL: API_BASE_URL,
})

export const AuthApi = {
  login(payload: LoginRequest) {
    return AuthAPIInstance.post<TokenResponse>('/auth/login', payload, {
      headers: {
        [SKIP_AUTH_REFRESH_HEADER]: 'true',
      },
    })
  },

  register(payload: RegisterRequest) {
    return AuthAPIInstance.post(
      '/auth/register',
      payload,
      {
        headers: {
          [SKIP_AUTH_REFRESH_HEADER]: 'true',
        },
      },
    )
  },

  refresh(refreshToken: string) {
    return AuthAPIInstance.post<TokenResponse>(
      '/auth/refresh',
      { refresh_token: refreshToken },
      {
        headers: {
          [SKIP_AUTH_REFRESH_HEADER]: 'true',
        },
      },
    )
  },

  me(token: string | null): Promise<AxiosResponse<UserProfile>> {
    return AuthAPIInstance.get<UserProfile>('/auth/me', {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
  },

  logout() {
    return DefaultAPIInstance.post(
      '/auth/logout',
      {},
      {
        headers: {
          [SKIP_AUTH_REFRESH_HEADER]: 'true',
        },
      },
    )
  },
}
