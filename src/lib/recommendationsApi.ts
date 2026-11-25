import type { Severity } from '@/data/mock'
import { useLiveSocket } from './useLiveSocket'

/** Sama bentuknya dengan `Insight` di data/mock.ts, jadi bisa langsung dipakai InsightCard. */
export interface Recommendation {
  id: string
  kind: string
  priority: Severity
  score: number
  title: string
  reason: string
  actions: string[]
  sources: string[]
  impact: string
  table: string | null
  mock: boolean
}

export interface RecommendationsSnapshot {
  now: number
  engine: 'rules' | 'rules+llm'
  summary: string
  rule_summary: string
  llm: { enabled: boolean; model?: string | null; reason?: string | null; error?: string | null }
  occupancy: number
  data_sources: Record<string, string>
  counts: Record<Severity, number>
  recommendations: Recommendation[] // sudah terurut prioritas dari backend
  source_status: { state: string; detail: string }
}

export function useRecommendationsLive() {
  return useLiveSocket<RecommendationsSnapshot>('/ws/recommendations')
}
