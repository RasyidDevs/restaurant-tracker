import { AlertTriangle, CalendarClock, Clock, CupSoda, Hourglass, Users, UtensilsCrossed } from 'lucide-react'
import { tableStatusMeta, type DiningTable } from '@/data/mock'
import { cn, formatMinutes } from '@/lib/utils'

export function TableCard({
  table,
  compact = false,
  selected = false,
  onClick,
}: {
  table: DiningTable
  compact?: boolean
  selected?: boolean
  onClick?: () => void
}) {
  const meta = tableStatusMeta[table.status]
  const seatsFilled = Array.from({ length: table.seats }, (_, i) => i < table.people)

  return (
    <button
      onClick={onClick}
      className={cn(
        'relative flex w-full flex-col rounded-xl border-2 p-3 text-left transition-all hover:shadow-md',
        meta.ring,
        meta.bg,
        selected && 'ring-2 ring-primary ring-offset-2 ring-offset-background',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">{table.name}</span>
        <span className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
          <span className={cn('h-2 w-2 rounded-full', meta.dot)} />
          {meta.label}
        </span>
      </div>

      {/* Kursi */}
      <div className="mt-2 flex flex-wrap gap-1">
        {seatsFilled.map((filled, i) => (
          <span
            key={i}
            className={cn(
              'h-2.5 w-2.5 rounded-full border',
              filled ? 'border-transparent bg-indigo-500' : 'bg-card',
            )}
          />
        ))}
      </div>

      {table.status === 'reserved' ? (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-violet-700 dark:text-violet-300">
          <CalendarClock className="h-3.5 w-3.5" />
          <span className="truncate">
            {table.reservedAt} · {table.reservedFor}
          </span>
        </div>
      ) : table.status === 'kosong' ? (
        <p className="mt-2 text-xs text-muted-foreground">Siap digunakan · {table.seats} kursi</p>
      ) : (
        <div className={cn('mt-2 grid gap-x-3 gap-y-1 text-xs', compact ? 'grid-cols-2' : 'grid-cols-2')}>
          <span className="flex items-center gap-1" title="Jumlah orang">
            <Users className="h-3.5 w-3.5 text-muted-foreground" /> {table.people}/{table.seats}
          </span>
          {table.durationMin > 0 && (
            <span className="flex items-center gap-1 tabular" title="Lama di meja">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" /> {formatMinutes(table.durationMin)}
            </span>
          )}
          <span className="flex items-center gap-1" title="Piring">
            <UtensilsCrossed className="h-3.5 w-3.5 text-muted-foreground" /> {table.plates}
          </span>
          <span className="flex items-center gap-1" title="Gelas">
            <CupSoda className="h-3.5 w-3.5 text-muted-foreground" /> {table.glasses}
          </span>
        </div>
      )}

      {!compact && table.estFreeMin !== undefined && (
        <div className="mt-2 flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-300">
          <Hourglass className="h-3.5 w-3.5" /> Kosong ±{table.estFreeMin}m ({table.estFreeConfidence}%)
        </div>
      )}

      {table.idleDishesMin !== undefined && (
        <div className="mt-2 flex items-center gap-1 text-xs font-medium text-rose-600 dark:text-rose-300">
          <AlertTriangle className="h-3.5 w-3.5" /> Tanpa orang {table.idleDishesMin}m
        </div>
      )}

      {table.outsideFood && (
        <span className="absolute -top-2 -right-2 rounded-full bg-orange-500 px-1.5 py-0.5 text-[10px] font-semibold text-white shadow">
          Makanan luar
        </span>
      )}
    </button>
  )
}
