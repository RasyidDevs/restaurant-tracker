import { useCallback } from 'react'
import type { AlertType, Severity } from '@/data/mock'
import { useLiveSocket, type SourceInfo } from '@/lib/liveSocket'

export type ParkingLevel = 'kosong' | 'normal' | 'mendekati' | 'lewat'

export interface ParkingSlotLive {
  id: string
  type: 'mobil' | 'motor'
  occupied: boolean
  vehicle_type: 'mobil' | 'motor'
  label: string | null
  track_id: number | null
  start: number | null
  duration_s: number
  duration_min: number
  limit_s: number
  limit_min: number
  over_s: number
  ratio: number
  level: ParkingLevel
  notified: boolean
  session_id: string | null
}

export interface ParkingCompleted {
  id: string
  slot_id: string
  vehicle_type: 'mobil' | 'motor'
  label: string
  start: number
  end: number | null
  duration_s: number
  limit_s: number
  over_s: number
  notified: boolean
}

export interface ParkingAlertItem {
  id: string
  kind: 'mendekati' | 'lewat'
  severity: Severity
  title: string
  message: string
  slot: string
  vehicle_type: 'mobil' | 'motor'
  label: string
  t: number
  resolved: boolean
}

export interface ParkingSnapshot {
  now: number
  mode: 'slots' | 'auto'
  source: SourceInfo
  rules: {
    car_limit_min: number
    bike_limit_min: number
    warn_ratio: number
    min_dwell_s: number
    lost_grace_s: number
  }
  slots: ParkingSlotLive[]
  warnings: ParkingSlotLive[]
  completed: ParkingCompleted[]
  alerts: ParkingAlertItem[]
  stats: {
    car_total: number
    car_occupied: number
    bike_total: number
    bike_occupied: number
    near_count: number
    over_count: number
    avg_duration_s: number | null
  }
}

export interface LiveAlertRecord {
  id: string
  type: AlertType
  severity: Severity
  title: string
  description: string
  location: string
  t: number
  camera: string
  resolved: boolean
}

export function useParkingLive() {
  const { data, conn } = useLiveSocket<ParkingSnapshot>('/ws/parking')

  const notifySlot = useCallback(async (slotId: string) => {
    const res = await fetch(`/api/parking/slots/${encodeURIComponent(slotId)}/notify`, { method: 'POST' })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as ParkingSlotLive
  }, [])

  return { data, conn, notifySlot }
}

export function useAlertsLive() {
  const { data, conn } = useLiveSocket<{ now: number; alerts: LiveAlertRecord[] }>('/ws/alerts')

  const resolveAlert = useCallback(async (alertId: string) => {
    const res = await fetch(`/api/alerts/${encodeURIComponent(alertId)}/resolve`, { method: 'POST' })
    if (!res.ok) throw new Error(await res.text())
  }, [])

  return { data, conn, resolveAlert }
}
