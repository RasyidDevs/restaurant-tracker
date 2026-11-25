import { Loader2, WifiOff } from 'lucide-react'
import { fmtClock, type ConnState, type SourceInfo } from '@/lib/liveSocket'
import { cn } from '@/lib/utils'

export function SourceBar({
  source,
  now,
  conn,
  commandHint = '.venv\\Scripts\\python -m app.main',
}: {
  source?: SourceInfo | null
  now?: number | null
  conn: ConnState
  commandHint?: string
}) {
  if (conn === 'offline' || (conn === 'connecting' && !source)) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
        {conn === 'offline' ? (
          <WifiOff className="mt-0.5 h-4 w-4 shrink-0" />
        ) : (
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
        )}
        <div>
          <p className="font-medium">{conn === 'offline' ? 'Backend CV belum terhubung' : 'Menghubungkan ke backend…'}</p>
          {conn === 'offline' && (
            <p className="mt-1">
              Jalankan di folder <code className="rounded bg-black/5 px-1 dark:bg-white/10">backend</code>:{' '}
              <code className="rounded bg-black/5 px-1 dark:bg-white/10">{commandHint}</code>
            </p>
          )}
        </div>
      </div>
    )
  }
  if (!source) return null
  const tone =
    source.state === 'running'
      ? 'bg-emerald-500'
      : source.state === 'error'
        ? 'bg-rose-500'
        : source.state === 'idle'
          ? 'bg-slate-400'
          : 'bg-amber-500'
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-sm">
      <span className={cn('h-2 w-2 rounded-full', tone, source.state === 'running' && 'animate-pulse')} />
      <span className="font-medium capitalize">{source.state}</span>
      <span className="text-muted-foreground">· {source.detail}</span>
      {now != null && now > 0 && (
        <span className="ml-auto text-xs text-muted-foreground tabular">waktu sumber {fmtClock(now)}</span>
      )}
    </div>
  )
}
