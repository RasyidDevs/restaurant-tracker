import { useEffect, useRef, useState } from 'react'
import { formatMinutes } from '@/lib/utils'

export type ConnState = 'connecting' | 'live' | 'offline'

export interface SourceInfo {
  state: 'starting' | 'loading' | 'running' | 'finished' | 'error' | 'idle'
  detail: string
}

/** Berlangganan snapshot JSON dari backend lewat WebSocket (auto-reconnect). */
export function useLiveSocket<T>(wsPath: string) {
  const [data, setData] = useState<T | null>(null)
  const [conn, setConn] = useState<ConnState>('connecting')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let closed = false
    let retry: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}${wsPath}`)
      wsRef.current = ws
      ws.onopen = () => setConn('live')
      ws.onmessage = (e) => {
        try {
          setData(JSON.parse(e.data) as T)
        } catch {
          /* abaikan pesan rusak */
        }
      }
      ws.onclose = () => {
        if (closed) return
        setConn('offline')
        retry = setTimeout(connect, 3000)
      }
      ws.onerror = () => ws.close()
    }
    connect()

    return () => {
      closed = true
      clearTimeout(retry)
      wsRef.current?.close()
    }
  }, [wsPath])

  return { data, conn }
}

/** 754 -> "12:34", 3725 -> "1:02:05" */
export function fmtDuration(sec: number | null | undefined) {
  if (sec == null) return '–'
  const s = Math.max(0, Math.round(sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** Tampilkan detik presisi ("1:15") bila < 2 menit (mode demo cepat), atau "2j 15m" untuk durasi normal. */
export function fmtSmartDuration(sec: number | null | undefined) {
  if (sec == null) return '–'
  if (sec < 120) return fmtDuration(sec)
  return formatMinutes(Math.round(sec / 60))
}

export function fmtClock(epoch: number | null | undefined) {
  if (epoch == null || epoch <= 0) return '–'
  return new Date(epoch * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
}
