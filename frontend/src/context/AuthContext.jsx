import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import api, { clearTokens, getTokens, setTokens } from '../api/client'

const AuthContext = createContext(null)

const IDLE_TIMEOUT_MS = 15 * 60 * 1000 // 15 minutes — mirrors backend SESSION_IDLE_TIMEOUT_MINUTES
const IDLE_WARNING_MS = 60 * 1000 // show a warning 60s before auto-logout

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [idleWarning, setIdleWarning] = useState(false)
  const idleTimerRef = useRef(null)
  const warningTimerRef = useRef(null)

  const logout = useCallback(async (silent = false) => {
    if (!silent) {
      try { await api.post('/auth/logout') } catch { /* best-effort */ }
    }
    clearTokens()
    setUser(null)
    setIdleWarning(false)
  }, [])

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current)
    setIdleWarning(false)

    if (!getTokens()) return

    warningTimerRef.current = setTimeout(() => {
      setIdleWarning(true)
    }, IDLE_TIMEOUT_MS - IDLE_WARNING_MS)

    idleTimerRef.current = setTimeout(() => {
      logout(true)
    }, IDLE_TIMEOUT_MS)
  }, [logout])

  // Track user activity to reset the idle timer
  useEffect(() => {
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart']
    const handler = () => resetIdleTimer()
    events.forEach((e) => window.addEventListener(e, handler))
    resetIdleTimer()
    return () => events.forEach((e) => window.removeEventListener(e, handler))
  }, [resetIdleTimer])

  // On mount: if tokens exist, validate them by fetching /auth/me
  useEffect(() => {
    const tokens = getTokens()
    if (!tokens?.access_token) {
      setLoading(false)
      return
    }
    api
      .get('/auth/me')
      .then(({ data }) => setUser(data))
      .catch(() => clearTokens())
      .finally(() => setLoading(false))
  }, [])

  const completeLogin = useCallback((tokenData) => {
    setTokens(tokenData)
    setUser({ username: tokenData.username, role: tokenData.role })
    resetIdleTimer()
  }, [resetIdleTimer])

  return (
    <AuthContext.Provider value={{ user, loading, completeLogin, logout, idleWarning, resetIdleTimer }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
