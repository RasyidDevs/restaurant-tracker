import { useCallback, useEffect, useRef, useState } from 'react'

export interface WaitingItem {
  kind: 'piring' | 'gelas'
  n: number
  t: number
}

export interface WaitingAlert {
  kind: 'belum_disajikan' | 'belum_lengkap'
  t: number
  message: string
  table?: string
}

export interface WaitingSession {
  id: string
  table_id: string
  start: number
  end: number | null
  status: 'menunggu' | 'sebagian' | 'lengkap' | 'pergi'
  end_reason: 'otomatis' | 'konfirmasi_waiter' | 'pelanggan_pergi' | null
  people_peak: number
  plates_served: number
  glasses_served: number
  required_glasses: number
  first_drink_at: number | null
  first_food_at: number | null
  last_item_at: number | null
  waiting_s: number
  first_drink_s: number | null
  first_food_s: number | null
  target_s: number
  alerts: WaitingAlert[]
  items: WaitingItem[]
}

export interface WaitingTable {
  id: string
  name: string
  seats: number
  phase: 'kosong' | 'menunggu' | 'disajikan'
  people: number
  people_raw: number
  plates: number
  glasses: number
  session: WaitingSession | null
}

export interface WaitingSnapshot {
  now: number
  source: { state: 'starting' | 'loading' | 'running' | 'finished' | 'error'; detail: string }
  rules: { target_min: number; alert_no_item_min: number; alert_partial_min: number; require_drinks: boolean }
  tables: WaitingTable[]
  active: WaitingSession[]
  completed: WaitingSession[]
  alerts: (WaitingAlert & { table: string })[]
  stats: {
    count: number
    left_count: number
    avg_wait_s: number | null
    median_wait_s: number | null
    max_wait_s: number | null
    avg_first_drink_s: number | null
    avg_first_food_s: number | null
    on_target_pct: number | null
    by_hour: { jam: string; rata_menit: number; jumlah: number }[]
  }
}

export type ConnState = 'connecting' | 'live' | 'offline'

/** Berlangganan snapshot waiting time dari backend lewat WebSocket (auto-reconnect). */
export function useWaitingLive() {
  const [data, setData] = useState<WaitingSnapshot | null>(null)
  const [conn, setConn] = useState<ConnState>('connecting')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let closed = false
    let retry: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/waiting`)
      wsRef.current = ws
      ws.onopen = () => setConn('live')
      ws.onmessage = (e) => {
        try {
          setData(JSON.parse(e.data))
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
  }, [])

  const confirm = useCallback(async (sessionId: string) => {
    const res = await fetch(`/api/sessions/${sessionId}/confirm`, { method: 'POST' })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as WaitingSession
  }, [])

  return { data, conn, confirm }
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

export function fmtClock(epoch: number | null | undefined) {
  if (epoch == null) return '–'
  return new Date(epoch * 1000).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
}
