<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getStoredUser,
  getNotebook,
  uploadDocument,
  getDocumentStatus,
} from '../api.js'
import ChatPanel from '../components/ChatPanel.vue'

const props = defineProps({
  id: { type: String, required: true },
})

const router = useRouter()
const user = getStoredUser()

const notebook = ref(null)
const documents = ref([]) // { document_id, name, type, status }
const loadError = ref('')
const uploadError = ref('')
const uploading = ref(false)

const fileInput = ref(null)
const isHandwritten = ref(false)

const TERMINAL_STATUSES = new Set(['done', 'failed', 'timeout'])
let pollTimer = null

// The backend has no "list documents for a notebook" endpoint (only
// GET /notebooks/{id}/documents/{document_id} for a single doc), so the
// document list can't be re-fetched from the server on page load. We
// persist it client-side per notebook so it survives navigating away and
// back within this browser.
const storageKey = `secondbrain_docs_${props.id}`

function loadDocumentsFromStorage() {
  try {
    const raw = localStorage.getItem(storageKey)
    documents.value = raw ? JSON.parse(raw) : []
  } catch (e) {
    documents.value = []
  }
}

function saveDocumentsToStorage() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(documents.value))
  } catch (e) {
    // ignore storage errors (e.g. private browsing quota)
  }
}

watch(documents, saveDocumentsToStorage, { deep: true })

async function loadNotebook() {
  loadError.value = ''
  try {
    notebook.value = await getNotebook(props.id)
  } catch (e) {
    loadError.value = e.message || 'Failed to load notebook.'
  }
}

async function handleUpload() {
  const file = fileInput.value?.files?.[0]
  if (!file) {
    uploadError.value = 'Choose a file first.'
    return
  }
  uploadError.value = ''
  uploading.value = true
  try {
    const result = await uploadDocument(props.id, user.user_id, file, isHandwritten.value)
    documents.value.push({
      document_id: result.document_id,
      name: file.name,
      type: result.type,
      status: result.status,
    })
    fileInput.value.value = ''
    isHandwritten.value = false
  } catch (e) {
    uploadError.value = e.message || 'Upload failed.'
  } finally {
    uploading.value = false
  }
}

async function pollStatuses() {
  const pending = documents.value.filter((d) => !TERMINAL_STATUSES.has(d.status))
  if (pending.length === 0) return
  await Promise.all(
    pending.map(async (doc) => {
      try {
        const result = await getDocumentStatus(props.id, doc.document_id)
        doc.status = result.status
      } catch (e) {
        // leave status as-is; will retry next tick
      }
    })
  )
}

onMounted(async () => {
  loadDocumentsFromStorage()
  await loadNotebook()
  pollTimer = setInterval(pollStatuses, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

function goToProfile() {
  router.push({ name: 'profile' })
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar card">
      <button class="secondary back-btn" @click="goToProfile">← Profile</button>
      <h2>Upload Document</h2>
      <div class="upload-form">
        <input ref="fileInput" type="file" />
        <label class="checkbox-row">
          <input type="checkbox" v-model="isHandwritten" />
          This is a handwritten note
        </label>
        <button @click="handleUpload" :disabled="uploading">
          {{ uploading ? 'Uploading…' : 'Upload' }}
        </button>
        <p v-if="uploadError" class="error-text">{{ uploadError }}</p>
      </div>
    </aside>

    <main class="content">
      <p v-if="loadError" class="error-text">{{ loadError }}</p>
      <template v-else-if="notebook">
        <h1>{{ notebook.title }}</h1>
        <div class="card">
          <h2>Documents</h2>
          <p v-if="documents.length === 0" class="muted">No documents uploaded yet.</p>
          <ul v-else class="doc-list">
            <li v-for="doc in documents" :key="doc.document_id">
              <span class="doc-name">{{ doc.name }}</span>
              <span class="status-badge" :class="`status-${doc.status}`">{{ doc.status }}</span>
            </li>
          </ul>
        </div>
        <ChatPanel :notebook-id="props.id" :user-id="user.user_id" />
      </template>
      <p v-else>Loading notebook…</p>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 280px;
  flex-shrink: 0;
  border-radius: 0;
  border-top: none;
  border-bottom: none;
  border-left: none;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}

.back-btn {
  align-self: flex-start;
}

.upload-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.checkbox-row input {
  width: auto;
}

.content {
  flex: 1;
  padding: 32px;
  max-width: 760px;
}

.muted {
  color: var(--muted);
}

.doc-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.doc-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.status-badge {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--border);
  color: var(--text-h);
}

.status-queued {
  background: #fef3c7;
  color: #92400e;
}

.status-done {
  background: #dcfce7;
  color: #166534;
}

.status-failed,
.status-timeout {
  background: #fee2e2;
  color: #991b1b;
}
</style>
