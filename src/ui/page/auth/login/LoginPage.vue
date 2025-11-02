<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useRouter, useRoute, type RouteLocationRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth-store'
import { Routes } from '@/config/router/routes'
import { AuthApi } from '@/domain/auth/api'
import { onMounted, watch } from 'vue'

type AuthMode = 'login' | 'register'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const mode = ref<AuthMode>('login')
const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  fullName: '',
  email: '',
})

const errorMessage = ref('')
const infoMessage = ref('')
const isSubmitting = ref(false)
const hasRedirected = ref(false)

const isRegisterMode = computed(() => mode.value === 'register')
const title = computed(() => (isRegisterMode.value ? 'Create account' : 'Sign in'))
const submitLabel = computed(() => {
  if (isRegisterMode.value) {
    return isBusy.value ? 'Creating account…' : 'Create account'
  }
  return isBusy.value ? 'Signing in…' : 'Sign in'
})

const isBusy = computed(() => isSubmitting.value || authStore.isAuthenticating)
const canSubmit = computed(() => {
  if (isRegisterMode.value) {
    return (
      form.username.trim().length > 0 &&
      form.password.length >= 8 &&
      form.confirmPassword.length >= 8 &&
      !isBusy.value
    )
  }
  return form.username.trim().length > 0 && form.password.length > 0 && !isBusy.value
})

const resetMessages = () => {
  errorMessage.value = ''
  infoMessage.value = ''
}

const resetForm = () => {
  form.username = ''
  form.password = ''
  form.confirmPassword = ''
  form.fullName = ''
  form.email = ''
}

const switchMode = () => {
  mode.value = isRegisterMode.value ? 'login' : 'register'
  resetMessages()
  resetForm()
  console.debug('[auth-view] switched mode', mode.value)
}

const resolveRedirectTarget = (): RouteLocationRaw => {
  const redirect =
    typeof route.query.redirect === 'string' && route.query.redirect.trim().length > 0
      ? route.query.redirect
      : null
  if (redirect) {
    return redirect
  }
  return { name: Routes.Chat }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const waitForSessionReady = async (timeoutMs = 1500) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (authStore.hasSession) {
      return true
    }
    await sleep(50)
  }
  return authStore.hasSession
}

const navigateAfterAuth = async () => {
  if (hasRedirected.value) return
  const ready = await waitForSessionReady()
  const target = resolveRedirectTarget()
  try {
    if (!ready) {
      console.warn('[auth-view] session not ready, forcing hard redirect', { target })
      if (typeof target === 'string') {
        window.location.replace(target)
      } else {
        const resolved = router.resolve(target)
        window.location.replace(resolved.href)
      }
      hasRedirected.value = true
      return
    }
    console.debug('[auth-view] navigateAfterAuth', { target })
    await router.replace(target)
    hasRedirected.value = true
    console.debug('[auth-view] navigation complete', {
      fullPath: router.currentRoute.value.fullPath,
    })
  } catch (error) {
    console.warn('[auth-view] navigation after auth failed', error)
  }
}

const handleSubmit = async (event: Event) => {
  event.preventDefault()
  if (!canSubmit.value || isBusy.value) return

  isSubmitting.value = true
  resetMessages()

  try {
    const username = form.username.trim()
    const password = form.password

    if (isRegisterMode.value) {
      if (password !== form.confirmPassword) {
        errorMessage.value = 'Passwords do not match.'
        return
      }

      await AuthApi.register({
        username,
        password,
        full_name: form.fullName.trim() || undefined,
        email: form.email.trim() || undefined,
      })

      infoMessage.value = 'Account created successfully. Signing you in…'

      await authStore.login({ username, password })
    } else {
      await authStore.login({ username, password })
    }

    await navigateAfterAuth()
  } catch (error: unknown) {
    const message =
      (error as Error)?.message ||
      (isRegisterMode.value
        ? 'Unable to create the account. Please try again.'
        : 'Unable to sign in. Please check your credentials and try again.')
    errorMessage.value = message
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  console.debug('[auth-view] mounted', {
    initialMode: mode.value,
    redirect: route.query.redirect,
  })
})

watch(
  () => authStore.hasSession,
  (hasSession) => {
    if (hasSession) {
      void navigateAfterAuth()
    }
  },
  { immediate: true },
)

watch(
  () => route.query.redirect,
  (value) => {
    console.debug('[auth-view] redirect query updated', value)
  },
)
</script>

<template>
  <div class="AuthPage">
    <form class="AuthPage__form" @submit="handleSubmit">
      <h1 class="AuthPage__title">{{ title }}</h1>

      <p class="AuthPage__subtitle">
        <span v-if="isRegisterMode">
          Already have an account?
          <button class="AuthPage__link" type="button" @click="switchMode">Sign in</button>
        </span>
        <span v-else>
          Need an account?
          <button class="AuthPage__link" type="button" @click="switchMode">Create one</button>
        </span>
      </p>

      <label class="AuthPage__field">
        <span class="AuthPage__label">Username</span>
        <input
          v-model="form.username"
          class="AuthPage__input"
          type="text"
          name="username"
          autocomplete="username"
          required
          :disabled="isBusy"
        />
      </label>

      <label v-if="isRegisterMode" class="AuthPage__field">
        <span class="AuthPage__label">Full name (optional)</span>
        <input
          v-model="form.fullName"
          class="AuthPage__input"
          type="text"
          name="fullName"
          autocomplete="name"
          :disabled="isBusy"
        />
      </label>

      <label v-if="isRegisterMode" class="AuthPage__field">
        <span class="AuthPage__label">Email (optional)</span>
        <input
          v-model="form.email"
          class="AuthPage__input"
          type="email"
          name="email"
          autocomplete="email"
          :disabled="isBusy"
        />
      </label>

      <label class="AuthPage__field">
        <span class="AuthPage__label">Password</span>
        <input
          v-model="form.password"
          class="AuthPage__input"
          type="password"
          name="password"
          :autocomplete="isRegisterMode ? 'new-password' : 'current-password'"
          required
          :disabled="isBusy"
          minlength="8"
        />
      </label>

      <label v-if="isRegisterMode" class="AuthPage__field">
        <span class="AuthPage__label">Confirm password</span>
        <input
          v-model="form.confirmPassword"
          class="AuthPage__input"
          type="password"
          name="confirm-password"
          autocomplete="new-password"
          required
          :disabled="isBusy"
          minlength="8"
        />
      </label>

      <p v-if="errorMessage" class="AuthPage__error">
        {{ errorMessage }}
      </p>
      <p v-else-if="infoMessage" class="AuthPage__info">
        {{ infoMessage }}
      </p>

      <button class="AuthPage__submit" type="submit" :disabled="!canSubmit">
        {{ submitLabel }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.AuthPage {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f8ff 0%, #e4ecff 100%);
  padding: 32px 16px;
  box-sizing: border-box;
}

.AuthPage__form {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 12px 32px rgba(38, 63, 118, 0.18);
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  font-family: var(--main_font, 'Inter', sans-serif);
}

.AuthPage__title {
  margin: 0;
  font-size: 26px;
  font-weight: 600;
  text-align: center;
  color: #1f2937;
}

.AuthPage__subtitle {
  margin: -8px 0 0;
  text-align: center;
  color: #4b5563;
  font-size: 14px;
}

.AuthPage__link {
  border: none;
  background: transparent;
  color: #2563eb;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.AuthPage__link:hover {
  text-decoration: underline;
}

.AuthPage__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.AuthPage__label {
  font-size: 14px;
  font-weight: 500;
  color: #4b5563;
}

.AuthPage__input {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  font-size: 14px;
  color: #1f2937;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.AuthPage__input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.AuthPage__input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}

.AuthPage__error {
  color: #dc2626;
  font-size: 14px;
  text-align: center;
  margin: 0;
}

.AuthPage__info {
  color: #2563eb;
  font-size: 14px;
  text-align: center;
  margin: 0;
}

.AuthPage__submit {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: none;
  background: #2563eb;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.AuthPage__submit:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.AuthPage__submit:not(:disabled):hover {
  background: #1d4ed8;
}

.AuthPage__submit:not(:disabled):active {
  transform: translateY(1px);
}
</style>
