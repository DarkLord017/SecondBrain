<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getStoredUser, clearStoredUser, listNotebooks, createNotebook } from '../api.js'

const router = useRouter()
const user = getStoredUser()

const notebooks = ref([])
const loading = ref(true)
const error = ref('')
const creating = ref(false)

async function loadNotebooks() {
  loading.value = true
  error.value = ''
  try {
    notebooks.value = await listNotebooks(user.user_id)
  } catch (e) {
    error.value = e.message || 'Failed to load notebooks.'
  } finally {
    loading.value = false
  }
}

async function handleCreateNotebook() {
  const title = window.prompt('Notebook title:')
  if (!title || !title.trim()) return
  creating.value = true
  error.value = ''
  try {
    const notebook = await createNotebook(user.user_id, title.trim())
    router.push({ name: 'notebook', params: { id: notebook.notebook_id } })
  } catch (e) {
    error.value = e.message || 'Failed to create notebook.'
  } finally {
    creating.value = false
  }
}

function handleLogout() {
  clearStoredUser()
  router.push({ name: 'login' })
}

onMounted(loadNotebooks)
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div>
        <h1>Profile</h1>
        <p class="muted">{{ user?.email }}</p>
      </div>
      <button class="secondary" @click="handleLogout">Log out</button>
    </header>

    <div class="card">
      <div class="row-header">
        <h2>Your Notebooks</h2>
        <button @click="handleCreateNotebook" :disabled="creating">
          {{ creating ? 'Creating…' : 'Create Notebook' }}
        </button>
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>
      <p v-if="loading">Loading notebooks…</p>
      <p v-else-if="notebooks.length === 0" class="muted">No notebooks yet. Create one to get started.</p>
      <ul v-else class="notebook-list">
        <li v-for="nb in notebooks" :key="nb.notebook_id">
          <router-link :to="{ name: 'notebook', params: { id: nb.notebook_id } }">
            {{ nb.title }}
          </router-link>
          <span class="muted small">{{ new Date(nb.created_at).toLocaleString() }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 16px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.muted {
  color: var(--muted);
  margin: 4px 0 0;
}

.row-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.notebook-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notebook-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.notebook-list a {
  font-weight: 600;
  color: var(--text-h);
}

.small {
  font-size: 13px;
}
</style>
