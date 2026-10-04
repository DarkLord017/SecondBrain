<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { signup, login, setStoredUser } from '../api.js'

const router = useRouter()

const mode = ref('login') // 'login' | 'signup'
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

function switchMode(next) {
  mode.value = next
  error.value = ''
}

async function handleSubmit() {
  error.value = ''
  if (!email.value || !password.value) {
    error.value = 'Email and password are required.'
    return
  }
  loading.value = true
  try {
    const action = mode.value === 'signup' ? signup : login
    const result = await action(email.value, password.value)
    setStoredUser({ user_id: result.user_id, email: result.email })
    router.push({ name: 'profile' })
  } catch (e) {
    if (mode.value === 'signup' && e.status === 409) {
      error.value = 'That email is already registered. Try logging in instead.'
    } else if (mode.value === 'login' && e.status === 401) {
      error.value = 'Incorrect email or password.'
    } else {
      error.value = e.message || 'Something went wrong.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="card login-card">
      <h1>SecondBrain</h1>
      <div class="tabs">
        <button
          :class="{ secondary: mode !== 'login' }"
          @click="switchMode('login')"
          type="button"
        >
          Log In
        </button>
        <button
          :class="{ secondary: mode !== 'signup' }"
          @click="switchMode('signup')"
          type="button"
        >
          Sign Up
        </button>
      </div>

      <form @submit.prevent="handleSubmit">
        <label>
          Email
          <input type="email" v-model="email" autocomplete="email" required />
        </label>
        <label>
          Password
          <input type="password" v-model="password" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Please wait…' : mode === 'signup' ? 'Create account' : 'Log in' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.login-card {
  width: 100%;
  max-width: 380px;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.tabs button {
  flex: 1;
}

form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-h);
}
</style>
