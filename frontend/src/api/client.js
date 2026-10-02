import axios from 'axios'

const api = axios.create({ baseURL: '/' })

// ── Token storage ──
// Access/refresh tokens are kept in memory + sessionStorage (NOT localStorage)
// so they clear automatically when the browser tab closes — reduces the window
// an attacker has if a device is compromised, matching the "session timeout"
// requirement more closely than persistent storage would.
export function getTokens() {
  try {
    return JSON.parse(sessionStorage.getItem('sdp_tokens') || 'null')
  } catch {
    return null
  }
}

export function setTokens(tokens) {
  sessionStorage.setItem('sdp_tokens', JSON.stringify(tokens))
}

export function clearTokens() {
  sessionStorage.removeItem('sdp_tokens')
}

// ── Request interceptor: attach access token ──
api.interceptors.request.use((config) => {
  const tokens = getTokens()
  if (tokens?.access_token) {
    config.headers.Authorization = `Bearer ${tokens.access_token}`
  }
  return config
})

// ── Response interceptor: auto-refresh on 401, retry once ──
let isRefreshing = false
let refreshQueue = []

function processQueue(error, token = null) {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  refreshQueue = []
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const status = error.response?.status

    // Don't try to refresh on the auth endpoints themselves
    const isAuthEndpoint = original?.url?.includes('/auth/login') || original?.url?.includes('/auth/mfa/verify') || original?.url?.includes('/auth/refresh')

    if (status === 401 && !original._retry && !isAuthEndpoint) {
      const tokens = getTokens()
      if (!tokens?.refresh_token) {
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Queue this request until the in-flight refresh completes
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject })
        }).then((newToken) => {
          original.headers.Authorization = `Bearer ${newToken}`
          return api(original)
        })
      }

      original._retry = true
      isRefreshing = true

      try {
        const { data } = await axios.post('/auth/refresh', { refresh_token: tokens.refresh_token })
        setTokens(data)
        processQueue(null, data.access_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return api(original)
      } catch (refreshError) {
        processQueue(refreshError, null)
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default api
