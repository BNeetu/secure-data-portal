import { useCallback, useEffect, useRef, useState } from 'react'
import api, { getTokens } from './client'

/**
 * Manages the file list for a (department, subdepartment, dataType) slot.
 * Returns { fileList, connected, refetch }
 *
 * The Dashboard fetches individual file dashboards separately via
 * /dashboard/{file_id} — this hook only maintains the list of what files
 * exist in the slot and signals when that list changes (new upload, delete).
 */
export function useLiveDashboard(department, subdepartment, dataType) {
  const [fileList,   setFileList]   = useState([])
  const [connected,  setConnected]  = useState(false)

  const wsRef             = useRef(null)
  const reconnectRef      = useRef(null)
  const pingRef           = useRef(null)
  const attemptRef        = useRef(0)
  const cancelRef         = useRef(false)

  // ── REST: fetch current file list ────────────────────────────────────────
  const refetch = useCallback(() => {
    if (!department || !subdepartment || !dataType) return
    const enc = s => encodeURIComponent(s)
    api.get(`/data/${enc(department)}/${enc(subdepartment)}/${enc(dataType)}/files`)
      .then(({ data }) => {
        if (!cancelRef.current) setFileList(data.files || [])
      })
      .catch(() => {})
  }, [department, subdepartment, dataType])

  // ── WebSocket: get notified when slot changes ─────────────────────────────
  useEffect(() => {
    if (!department || !subdepartment || !dataType) return
    cancelRef.current = false
    setFileList([])
    setConnected(false)

    refetch()   // initial load
    const refreshInterval = setInterval(refetch, 15000)

    function connect() {
      const tokens = getTokens()
      if (!tokens?.access_token || cancelRef.current) return

      const proto  = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const params = new URLSearchParams({
        department, subdepartment, data_type: dataType,
        token: tokens.access_token,
      })
      const ws = new WebSocket(`${proto}//${window.location.host}/data/ws/live?${params}`)
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelRef.current) return
        setConnected(true)
        attemptRef.current = 0
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping')
        }, 25000)
      }

      ws.onmessage = event => {
        if (event.data === 'pong' || cancelRef.current) return
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'slot_updated'
            && msg.department    === department
            && msg.subdepartment === subdepartment
            && msg.data_type     === dataType) {
            refetch()   // slot changed → refresh the file list
          }
        } catch { /* ignore */ }
      }

      ws.onclose = () => {
        if (cancelRef.current) return
        setConnected(false)
        clearInterval(pingRef.current)
        const delay = Math.min(12000, 800 * 2 ** attemptRef.current)
        attemptRef.current += 1
        reconnectRef.current = setTimeout(connect, delay)
      }

      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      cancelRef.current = true
      clearInterval(refreshInterval)
      clearTimeout(reconnectRef.current)
      clearInterval(pingRef.current)
      wsRef.current?.close()
    }
  }, [department, subdepartment, dataType, refetch])

  return { fileList, connected, refetch }
}
