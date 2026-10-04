const BASE_URL = 'http://127.0.0.1:8000'
const STORAGE_KEY = 'secondbrain_user'

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

export function setStoredUser(user) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
}

export function clearStoredUser() {
  localStorage.removeItem(STORAGE_KEY)
}

async function parseErrorMessage(res) {
  try {
    const body = await res.json()
    if (body.detail) {
      return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    }
    return JSON.stringify(body)
  } catch (e) {
    return `Request failed with status ${res.status}`
  }
}

export async function signup(email, password) {
  const res = await fetch(`${BASE_URL}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const message = await parseErrorMessage(res)
    const err = new Error(message)
    err.status = res.status
    throw err
  }
  return res.json()
}

export async function login(email, password) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const message = await parseErrorMessage(res)
    const err = new Error(message)
    err.status = res.status
    throw err
  }
  return res.json()
}

export async function createNotebook(userId, title) {
  const res = await fetch(`${BASE_URL}/notebooks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, title }),
  })
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res))
  }
  return res.json()
}

export async function listNotebooks(userId) {
  const res = await fetch(`${BASE_URL}/notebooks?user_id=${encodeURIComponent(userId)}`)
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res))
  }
  return res.json()
}

export async function getNotebook(notebookId) {
  const res = await fetch(`${BASE_URL}/notebooks/${encodeURIComponent(notebookId)}`)
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res))
  }
  return res.json()
}

export async function uploadDocument(notebookId, userId, file, isHandwritten) {
  const formData = new FormData()
  formData.append('user_id', userId)
  formData.append('file', file)
  formData.append('is_handwritten', isHandwritten ? 'true' : 'false')

  const res = await fetch(`${BASE_URL}/notebooks/${encodeURIComponent(notebookId)}/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res))
  }
  return res.json()
}

export async function sendChatMessage(notebookId, userId, question) {
  const res = await fetch(`${BASE_URL}/notebooks/${encodeURIComponent(notebookId)}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, question }),
  })
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res))
  }
  return res.json()
}

export function runWebSocketUrl(runId) {
  const wsBase = BASE_URL.replace(/^http/, 'ws')
  return `${wsBase}/ws/runs/${encodeURIComponent(runId)}`
}

export async function getDocumentStatus(notebookId, documentId) {
  const res = await fetch(
    `${BASE_URL}/notebooks/${encodeURIComponent(notebookId)}/documents/${encodeURIComponent(documentId)}`
  )
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res))
  }
  return res.json()
}

export async function getRun(runId) {
  const res = await fetch(`${BASE_URL}/runs/${encodeURIComponent(runId)}`)
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res))
  }
  return res.json()
}
