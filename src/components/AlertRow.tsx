import { Link } from 'react-router-dom'
import { CalendarClock, Car, Clock, PackageX, UtensilsCrossed, type LucideIcon } from 'lucide-react'
import type { AlertItem, AlertType, Severity } from '@/data/mock'
import { Badge, type BadgeVariant } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export const alertTypeMeta: Record<AlertType, { label: string; icon: LucideIcon; tone: string; href: string }> = {
  'makanan-luar': { label: 'Makanan Luar', icon: PackageX, tone: 'bg-orange-100 text-orange-600 dark:bg-orange-500/15 dark:text-orange-300', href: '/meja' },
  'piring-tanpa-orang': { label: 'Piring Tanpa Orang', icon: UtensilsCrossed, tone: 'bg-rose-100 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300', href: '/meja' },
  'parkir-lama': { label: 'Parkir Lama', icon: Car, tone: 'bg-sky-100 text-sky-600 dark:bg-sky-500/15 dark:text-sky-300', href: '/parkir' },
  'waiting-lama': { label: 'Waiting Lama', icon: Clock, tone: 'bg-amber-100 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300', href: '/waiting-time' },
  reservasi: { label: 'Reservasi', icon: CalendarClock, tone: 'bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300', href: '/meja' },
}

export const severityVariant: Record<Severity, BadgeVariant> = {
  tinggi: 'danger',
  sedang: 'warning',
  rendah: 'info',
}

export function AlertRow({
  alert,
  showActions = false,
  onResolve,
}: {
  alert: AlertItem
  showActions?: boolean
  onResolve?: (id: string) => void
}) {
  const meta = alertTypeMeta[alert.type]
  const Icon = meta.icon
  return (
    <div className={cn('flex gap-3 rounded-lg border p-3', alert.resolved && 'opacity-60')}>
      <div className={cn('h-fit rounded-lg p-2', meta.tone)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium">{alert.title}</p>
          <Badge variant={severityVariant[alert.severity]}>{alert.severity}</Badge>
          {alert.resolved && <Badge variant="success">selesai</Badge>}
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">{alert.description}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {alert.location} · {alert.camera} · {alert.time}
        </p>
        {showActions && !alert.resolved && (
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              onClick={() => onResolve?.(alert.id)}
              className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:opacity-90"
            >
              Tangani
            </button>
            <Link to={meta.href} className="rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted">
              Lihat detail
            </Link>
            <button
              onClick={() => onResolve?.(alert.id)}
              className="rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted"
            >
              Abaikan
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
