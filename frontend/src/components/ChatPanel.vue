<script setup>
import { ref, reactive, nextTick, onUnmounted } from 'vue'
import { sendChatMessage, runWebSocketUrl, getRun } from '../api.js'

const props = defineProps({
  notebookId: { type: String, required: true },
  userId: { type: String, required: true },
})

const messages = ref([]) // { role: 'user'|'assistant', text, status, verifying, error, citationCount, citationFlags }
const input = ref('')
const sending = ref(false)
const messagesEl = ref(null)

let socket = null
let pollTimer = null

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

function cleanupConnections() {
  if (socket) {
    socket.onmessage = null
    socket.onopen = null
    socket.onerror = null
    socket.onclose = null
    try {
      socket.close()
    } catch (e) {
      // ignore
    }
    socket = null
  }
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function finishRun() {
  sending.value = false
  cleanupConnections()
}

function pollFallback(runId, msg) {
  pollTimer = setInterval(async () => {
    try {
      const run = await getRun(runId)
      if (run.status === 'done') {
        msg.text = run.final_answer || ''
        msg.status = 'done'
        finishRun()
        scrollToBottom()
      } else if (run.status === 'error') {
        msg.status = 'error'
        msg.error = run.error || 'The run failed.'
        finishRun()
        scrollToBottom()
      }
    } catch (e) {
      // keep retrying until it resolves
    }
  }, 2000)
}

function openSocket(runId, msg) {
  let opened = false
  const ws = new WebSocket(runWebSocketUrl(runId))
  socket = ws

  ws.onopen = () => {
    opened = true
  }

  ws.onmessage = (event) => {
    let frame
    try {
      frame = JSON.parse(event.data)
    } catch (e) {
      return
    }

    if (frame.type === 'token') {
      msg.text += frame.data
    } else if (frame.type === 'status') {
      if (frame.data === 'verifying_citations') {
        msg.verifying = true
      }
    } else if (frame.type === 'final') {
      msg.verifying = false
      msg.text = frame.data.answer
      msg.citationCount = (frame.data.citations || []).length
      msg.citationFlags = frame.data.citation_flags || []
      msg.status = 'done'
      finishRun()
    } else if (frame.type === 'error') {
      msg.verifying = false
      msg.status = 'error'
      msg.error = frame.data
      finishRun()
    }
    scrollToBottom()
  }

  ws.onerror = () => {
    if (!opened && sending.value) {
      // WS never opened successfully; fall back to polling the run status.
      cleanupConnections()
      pollFallback(runId, msg)
    }
  }

  ws.onclose = () => {
    if (sending.value && msg.status !== 'done' && msg.status !== 'error') {
      if (!opened) {
        pollFallback(runId, msg)
      } else {
        msg.status = 'error'
        msg.error = 'Connection closed unexpectedly.'
        finishRun()
        scrollToBottom()
      }
    }
  }
}

async function send() {
  const question = input.value.trim()
  if (!question || sending.value) return

  input.value = ''
  messages.value.push({ role: 'user', text: question })

  // `reactive()` (not a plain object) so that mutating this object directly
  // inside the WebSocket handler — msg.text += token, msg.verifying = true,
  // etc. — goes through Vue's reactive setters and triggers a re-render on
  // every single frame. A plain object pushed into a ref([]) array only
  // becomes reactive when read back *through* the array's proxy; mutating
  // the original raw reference (as openSocket does below) would silently
  // bypass tracking, so the UI would only catch up on some later, unrelated
  // reactive update (e.g. sending.value = false) and the whole answer would
  // appear to pop in at once instead of streaming token by token.
  const assistantMsg = reactive({
    role: 'assistant',
    text: '',
    status: 'streaming',
    verifying: false,
    error: '',
    citationCount: 0,
    citationFlags: [],
  })
  messages.value.push(assistantMsg)
  sending.value = true
  scrollToBottom()

  try {
    const ack = await sendChatMessage(props.notebookId, props.userId, question)
    openSocket(ack.run_id, assistantMsg)
  } catch (e) {
    assistantMsg.status = 'error'
    assistantMsg.error = e.message || 'Failed to send message.'
    sending.value = false
  }
}

onUnmounted(() => {
  cleanupConnections()
})
</script>

<template>
  <div class="chat-panel card">
    <h2>Ask about this notebook</h2>
    <div ref="messagesEl" class="messages">
      <p v-if="messages.length === 0" class="muted">
        Ask a question about the documents you've uploaded.
      </p>
      <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
        <div class="bubble" :class="msg.role">
          <template v-if="msg.role === 'user'">{{ msg.text }}</template>
          <template v-else>
            <span v-if="msg.text">{{ msg.text }}</span>
            <span v-else-if="msg.status === 'streaming'" class="muted">Thinking…</span>
            <p v-if="msg.verifying" class="status-note">Verifying citations…</p>
            <p v-if="msg.status === 'error'" class="error-text">{{ msg.error }}</p>
            <template v-if="msg.status === 'done'">
              <p v-if="msg.citationCount" class="muted citation-count">
                {{ msg.citationCount }} source{{ msg.citationCount === 1 ? '' : 's' }}
              </p>
              <details v-if="msg.citationFlags && msg.citationFlags.length" class="citation-warning">
                <summary>⚠ {{ msg.citationFlags.length }} citation(s) could not be verified</summary>
                <ul>
                  <li v-for="(flag, fi) in msg.citationFlags" :key="fi">
                    <strong>{{ flag.verdict }}</strong>: {{ flag.reason }}
                  </li>
                </ul>
              </details>
            </template>
          </template>
        </div>
      </div>
    </div>
    <form class="chat-input-row" @submit.prevent="send">
      <input
        type="text"
        v-model="input"
        placeholder="Ask a question about this notebook…"
        :disabled="sending"
      />
      <button type="submit" :disabled="sending || !input.trim()">
        {{ sending ? 'Working…' : 'Send' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 24px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  min-height: 120px;
  overflow-y: auto;
  padding-right: 4px;
}

.message-row {
  display: flex;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble.user {
  background: var(--accent);
  color: #fff;
}

.bubble.assistant {
  background: var(--accent-bg);
  color: var(--text);
  border: 1px solid var(--border);
}

.status-note {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--muted);
  font-style: italic;
}

.citation-count {
  margin: 6px 0 0;
  font-size: 12px;
}

.citation-warning {
  margin-top: 6px;
  font-size: 12px;
  color: #92400e;
}

.citation-warning summary {
  cursor: pointer;
  font-weight: 600;
}

.citation-warning ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.chat-input-row {
  display: flex;
  gap: 10px;
}

.chat-input-row input {
  flex: 1;
}
</style>
