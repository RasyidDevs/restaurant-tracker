import { useCallback } from 'react'
import { fmtClock, fmtDuration, useLiveSocket, type ConnState, type SourceInfo } from '@/lib/liveSocket'

export { fmtClock, fmtDuration, type ConnState }

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
  source: SourceInfo
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

export function useWaitingLive() {
  const { data, conn } = useLiveSocket<WaitingSnapshot>('/ws/waiting')

  const confirm = useCallback(async (sessionId: string) => {
    const res = await fetch(`/api/sessions/${sessionId}/confirm`, { method: 'POST' })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as WaitingSession
  }, [])

  return { data, conn, confirm }
}
