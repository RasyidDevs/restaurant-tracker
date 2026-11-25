import { CheckCircle2, Sparkles, TrendingUp } from 'lucide-react'
import type { Insight } from '@/data/mock'
import { Badge } from '@/components/ui/badge'
import { severityVariant } from './AlertRow'
import { cn } from '@/lib/utils'

export function InsightCard({ insight, compact = false }: { insight: Insight; compact?: boolean }) {
  return (
    <div
      className={cn(
        'rounded-xl border p-4',
        insight.priority === 'tinggi' && 'border-l-4 border-l-rose-500',
        insight.priority === 'sedang' && 'border-l-4 border-l-amber-500',
        insight.priority === 'rendah' && 'border-l-4 border-l-sky-500',
      )}
    >
      <div className="flex items-start gap-2">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{insight.title}</p>
            <Badge variant={severityVariant[insight.priority]}>prioritas {insight.priority}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{insight.reason}</p>

          {!compact && (
            <>
              <ul className="mt-3 space-y-1.5">
                {insight.actions.map((a) => (
                  <li key={a} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                    {a}
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Sumber data:</span>
                {insight.sources.map((s) => (
                  <Badge key={s}>{s}</Badge>
                ))}
              </div>
            </>
          )}

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <span className="flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
              <TrendingUp className="h-3.5 w-3.5" /> {insight.impact}
            </span>
            {!compact && (
              <div className="flex gap-2">
                <button className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground">
                  Jalankan aksi
                </button>
                <button className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted">
                  Tunda
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
