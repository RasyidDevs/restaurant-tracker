import { Bike, Car, CircleParking, Siren } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { StatCard } from '@/components/ui/stat-card'
import { parkingSlots, type ParkingSlot } from '@/data/mock'
import { cn, formatMinutes } from '@/lib/utils'

function level(p: ParkingSlot) {
  if (!p.plate) return 'kosong'
  const r = p.durationMin / p.limitMin
  if (r > 1) return 'lewat'
  if (r >= 0.85) return 'mendekati'
  return 'normal'
}

const levelStyle = {
  kosong: 'border-dashed bg-transparent text-muted-foreground',
  normal: 'border-emerald-300 bg-emerald-50 dark:border-emerald-500/40 dark:bg-emerald-500/10',
  mendekati: 'border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10',
  lewat: 'border-rose-400 bg-rose-50 dark:border-rose-500/50 dark:bg-rose-500/10',
}

export default function Parking() {
  const cars = parkingSlots.filter((p) => p.type === 'mobil')
  const bikes = parkingSlots.filter((p) => p.type === 'motor')
  const over = parkingSlots.filter((p) => level(p) === 'lewat')
  const near = parkingSlots.filter((p) => level(p) === 'mendekati')
  const watch = [...over, ...near].sort((a, b) => b.durationMin / b.limitMin - a.durationMin / a.limitMin)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Mobil" value={`${cars.filter((c) => c.plate).length}/${cars.length}`} hint="slot terisi" icon={Car} />
        <StatCard label="Motor" value={`${bikes.filter((c) => c.plate).length}/${bikes.length}`} hint="slot terisi" icon={Bike} tone="sky" />
        <StatCard label="Mendekati Batas" value={`${near.length}`} hint="≥ 85% batas waktu" icon={CircleParking} tone="amber" />
        <StatCard label="Melewati Batas" value={`${over.length}`} hint="perlu tindakan" icon={Siren} tone="rose" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <SlotGrid title="Area Parkir Mobil" desc="Batas 3 jam · CAM-P1" slots={cars} icon={Car} cols="grid-cols-2 sm:grid-cols-4" />
          <SlotGrid title="Area Parkir Motor" desc="Batas 2 jam · CAM-P2" slots={bikes} icon={Bike} cols="grid-cols-3 sm:grid-cols-6" />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Peringatan Parkir</CardTitle>
            <CardDescription>Diurutkan dari yang paling lama</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {watch.map((p) => {
              const l = level(p)
              return (
                <div key={p.id} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {p.type === 'mobil' ? <Car className="h-4 w-4" /> : <Bike className="h-4 w-4" />}
                      <span className="font-semibold">{p.plate}</span>
                    </div>
                    <Badge variant={l === 'lewat' ? 'danger' : 'warning'}>
                      {l === 'lewat' ? `+${formatMinutes(p.durationMin - p.limitMin)}` : 'mendekati'}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Slot {p.id} · {formatMinutes(p.durationMin)} dari batas {formatMinutes(p.limitMin)}
                  </p>
                  <Progress value={(p.durationMin / p.limitMin) * 100} className="mt-2" barClassName={l === 'lewat' ? 'bg-rose-500' : 'bg-amber-500'} />
                  {l === 'lewat' && (
                    <button className="mt-2 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground">
                      Kirim ke juru parkir
                    </button>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function SlotGrid({
  title,
  desc,
  slots,
  icon: Icon,
  cols,
}: {
  title: string
  desc: string
  slots: ParkingSlot[]
  icon: typeof Car
  cols: string
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{desc}</CardDescription>
        </div>
        <div className="hidden gap-3 text-xs text-muted-foreground sm:flex">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" />Normal</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" />Mendekati</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500" />Lewat</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className={cn('grid gap-2', cols)}>
          {slots.map((p) => {
            const l = level(p)
            return (
              <div key={p.id} className={cn('rounded-lg border-2 p-2 text-xs', levelStyle[l])}>
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{p.id}</span>
                  {p.plate && <Icon className="h-3.5 w-3.5" />}
                </div>
                {p.plate ? (
                  <>
                    <p className="mt-1 truncate font-medium">{p.plate}</p>
                    <p className={cn('tabular', l === 'lewat' && 'font-semibold text-rose-600 dark:text-rose-400')}>
                      {formatMinutes(p.durationMin)}
                    </p>
                  </>
                ) : (
                  <p className="mt-1">Kosong</p>
                )}
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
