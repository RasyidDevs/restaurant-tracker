import { useEffect, useState } from 'react'
import type { DiningTable, TableStatus } from '@/data/mock'
import type { ConnState } from '@/lib/waitingApi'

export type OccupancyStatus = 'kosong' | 'terisi' | 'segera_kosong' | 'perlu_dibersihkan'
export type VisitPhase = 'menunggu_makanan' | 'makan' | 'selesai_makan'

export interface TableEstimate {
  est_free_s: number
  est_free_min: number
  est_free_at: number
  confidence: number
  soon_free: boolean
  reason: string
}

export interface Visit {
  id: string
  table_id: string
  start: number
  end: number | null
  people_peak: number
  phase: VisitPhase
  duration_s: number
  first_food_at: number | null
  cleared_at: number | null
  food_wait_s: number | null
  post_food_s: number | null
}

export interface OccupancyTable {
  id: string
  name: string
  seats: number
  people: number
  people_raw: number
  plates: number
  glasses: number
  seats_occupied: number | null
  seat_flags: boolean[] | null
  occupied_since: number | null
  occupied_s: number
  empty_s: number
  status: OccupancyStatus
  seats_free: number
  visit: Visit | null
  estimate: TableEstimate | null
}

export interface OccupancySnapshot {
  now: number
  source: { state: 'starting' | 'loading' | 'running' | 'finished' | 'error'; detail: string }
  tables: OccupancyTable[]
  summary: {
    people: number
    seats: number
    seat_util_pct: number
    tables_total: number
    tables_occupied: number
    tables_free: number
    soon_free: number
  }
  soon_free: (TableEstimate & { id: string; name: string })[]
  learned: { food_wait_s: number | null; post_food_s: number | null; samples: number }
  visits: Visit[]
  stats: {
    count: number
    avg_dwell_s: number | null
    median_dwell_s: number | null
    max_dwell_s: number | null
    avg_group_size: number | null
    distribution: { rentang: string; meja: number }[]
    by_group_size: { orang: number; rata_menit: number; jumlah: number }[]
  }
}

/** Berlangganan snapshot okupansi meja dari backend lewat WebSocket (auto-reconnect). */
export function useOccupancyLive() {
  const [data, setData] = useState<OccupancySnapshot | null>(null)
  const [conn, setConn] = useState<ConnState>('connecting')

  useEffect(() => {
    let closed = false
    let ws: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/occupancy`)
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
      ws.onerror = () => ws?.close()
    }
    connect()

    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [])

  return { data, conn }
}

const statusMap: Record<OccupancyStatus, TableStatus> = {
  kosong: 'kosong',
  terisi: 'terisi',
  segera_kosong: 'segera-kosong',
  perlu_dibersihkan: 'perlu-dibersihkan',
}

export const phaseLabel: Record<VisitPhase, string> = {
  menunggu_makanan: 'Menunggu makanan',
  makan: 'Sedang makan',
  selesai_makan: 'Selesai makan',
}

/** Ubah meja dari backend ke bentuk DiningTable yang dipakai TableCard. */
export function toDiningTable(t: OccupancyTable): DiningTable {
  return {
    id: t.id,
    name: t.name,
    seats: t.seats,
    zone: 'Indoor',
    status: statusMap[t.status],
    people: t.people,
    durationMin: Math.round(t.occupied_s / 60),
    plates: t.plates,
    glasses: t.glasses,
    estFreeMin: t.estimate?.est_free_min,
    estFreeConfidence: t.estimate?.confidence,
    estFreeReason: t.estimate?.reason,
    phase: t.visit ? phaseLabel[t.visit.phase] : undefined,
  }
}
