import { useCallback } from 'react'
import { useLiveSocket } from './useLiveSocket'

export interface OutsideFoodAlert {
  id: string
  table: string
  table_name: string
  kind: string
  label: string
  category: 'minuman' | 'makanan'
  confidence: number // rata-rata, 0-1
  max_confidence: number
  first_seen: number // epoch detik
  t: number // waktu alert dibuat
  last_seen: number
  status: 'active' | 'resolved'
  end_reason: 'objek_hilang' | 'ditangani_staf' | null
  ended_at: number | null
  source: 'cv' | 'mock'
}

export interface OutsideFoodRules {
  conf_threshold: number
  min_persist_s: number
  min_hit_ratio: number
  clear_after_s: number
  cooldown_s: number
  require_occupied: boolean
  ignore_kinds: string[]
}

export interface OutsideFoodSnapshot {
  now: number
  source: 'cv' | 'mock'
  source_status: { state: string; detail: string }
  rules: OutsideFoodRules
  active: OutsideFoodAlert[]
  history: OutsideFoodAlert[]
  tables: { id: string; name: string; people: number; flagged: boolean }[]
  stats: {
    active_count: number
    total_count: number
    handled_count: number
    by_kind: { label: string; jumlah: number }[]
  }
}

/** Alert makanan/minuman dari luar, live dari backend. */
export function useOutsideFoodLive() {
  const { data, conn } = useLiveSocket<OutsideFoodSnapshot>('/ws/outside-food')

  const resolve = useCallback(async (id: string) => {
    const res = await fetch(`/api/outside-food/${id}/resolve`, { method: 'POST' })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as OutsideFoodAlert
  }, [])

  return { data, conn, resolve }
}
