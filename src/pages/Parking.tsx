import { useState } from 'react'
import { Bike, Car, Check, CircleParking, Loader2, Siren, Video } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { StatCard } from '@/components/ui/stat-card'
import { SourceBar } from '@/components/SourceBar'
import { fmtClock, fmtSmartDuration } from '@/lib/liveSocket'
import { useParkingLive, type ParkingLevel, type ParkingSlotLive } from '@/lib/parkingApi'
import { cn } from '@/lib/utils'

const levelStyle: Record<ParkingLevel, string> = {
  kosong: 'border-dashed bg-transparent text-muted-foreground',
  normal: 'border-emerald-300 bg-emerald-50 dark:border-emerald-500/40 dark:bg-emerald-500/10',
  mendekati: 'border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10',
  lewat: 'border-rose-400 bg-rose-50 dark:border-rose-500/50 dark:bg-rose-500/10',
}

export default function Parking() {
  const { data, conn, notifySlot } = useParkingLive()
  const [busy, setBusy] = useState<string | null>(null)

  const onNotify = async (slotId: string) => {
    setBusy(slotId)
    try {
      await notifySlot(slotId)
    } finally {
      setBusy(null)
    }
  }

  const slots = data?.slots ?? []
  const cars = slots.filter((p) => p.type === 'mobil')
  const bikes = slots.filter((p) => p.type === 'motor')
  const watch = data?.warnings ?? []
  const carLimS = (data?.rules.car_limit_min ?? 180) * 60
  const bikeLimS = (data?.rules.bike_limit_min ?? 120) * 60
  const warnPct = Math.round((data?.rules.warn_ratio ?? 0.85) * 100)
  const isAuto = data?.mode === 'auto'

  const isSim = Boolean(data?.source.detail.startsWith('Mode simulasi'))
  const streamReady =
    conn === 'live' &&
    Boolean(data) &&
    !isSim &&
    (data?.source.state === 'running' || data?.source.state === 'finished')
  const streamLoading =
    conn === 'live' && Boolean(data) && !isSim && (data?.source.state === 'starting' || data?.source.state === 'loading')

  return (
    <div className="space-y-6">
      <SourceBar
        source={data?.source}
        now={data?.now}
        conn={conn}
        commandHint=".venv\Scripts\python -m app.main --source videos\meja.mp4 --parking-source videos\parkir.mp4"
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Mobil"
          value={isAuto ? `${data?.stats.car_occupied ?? 0}` : `${data?.stats.car_occupied ?? 0}/${data?.stats.car_total ?? 0}`}
          hint={isAuto ? 'terdeteksi parkir' : 'slot terisi'}
          icon={Car}
        />
        <StatCard
          label="Motor"
          value={isAuto ? `${data?.stats.bike_occupied ?? 0}` : `${data?.stats.bike_occupied ?? 0}/${data?.stats.bike_total ?? 0}`}
          hint={isAuto ? 'terdeteksi parkir' : 'slot terisi'}
          icon={Bike}
          tone="sky"
        />
        <StatCard
          label="Mendekati Batas"
          value={`${data?.stats.near_count ?? 0}`}
          hint={`≥ ${warnPct}% batas waktu`}
          icon={CircleParking}
          tone="amber"
        />
        <StatCard
          label="Melewati Batas"
          value={`${data?.stats.over_count ?? 0}`}
          hint="perlu tindakan"
          icon={Siren}
          tone="rose"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          {(streamReady || streamLoading) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Video className="h-4 w-4" /> Kamera & Deteksi Parkiran
                </CardTitle>
                <CardDescription>
                  Hijau = normal, kuning = mendekati batas, merah = lewat batas, tipis = kendaraan melintas
                </CardDescription>
              </CardHeader>
              <CardContent>
                {streamReady ? (
                  <img
                    src="/api/parking/stream.mjpg"
                    alt="Stream kamera parkiran beranotasi"
                    className="w-full rounded-lg bg-slate-900"
                  />
                ) : (
                  <div className="flex aspect-video items-center justify-center gap-2 rounded-lg bg-slate-900 text-xs text-slate-300">
                    <Loader2 className="h-5 w-5 animate-spin" /> Memuat model YOLO & membuka video parkiran…
                  </div>
                )}
              </CardContent>
            </Card>
          )}
          <SlotGrid
            title="Area Parkir Mobil"
            desc={`Batas ${fmtSmartDuration(carLimS)} · CAM-P1`}
            slots={cars}
            icon={Car}
            cols="grid-cols-2 sm:grid-cols-4"
            emptyText={conn === 'offline' ? 'Backend belum terhubung.' : 'Belum ada mobil parkir di area ini.'}
          />
          <SlotGrid
            title="Area Parkir Motor"
            desc={`Batas ${fmtSmartDuration(bikeLimS)} · CAM-P2`}
            slots={bikes}
            icon={Bike}
            cols="grid-cols-3 sm:grid-cols-6"
            emptyText={conn === 'offline' ? 'Backend belum terhubung.' : 'Belum ada motor parkir di area ini.'}
          />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Peringatan Parkir</CardTitle>
            <CardDescription>Diurutkan dari yang paling lama</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!watch.length ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                {conn === 'offline' ? 'Backend belum terhubung.' : 'Semua kendaraan masih dalam batas aman.'}
              </p>
            ) : (
              watch.map((p) => {
                const isOver = p.level === 'lewat'
                return (
                  <div key={p.id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {p.vehicle_type === 'mobil' ? <Car className="h-4 w-4" /> : <Bike className="h-4 w-4" />}
                        <span className="font-semibold">{p.label ?? p.id}</span>
                      </div>
                      <Badge variant={isOver ? 'danger' : 'warning'}>
                        {isOver ? `+${fmtSmartDuration(p.over_s)}` : 'mendekati'}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Slot {p.id} · masuk {fmtClock(p.start)} · {fmtSmartDuration(p.duration_s)} dari batas{' '}
                      {fmtSmartDuration(p.limit_s)}
                    </p>
                    <Progress
                      value={p.ratio * 100}
                      className="mt-2"
                      barClassName={isOver ? 'bg-rose-500' : 'bg-amber-500'}
                    />
                    {isOver && (
                      <button
                        onClick={() => onNotify(p.id)}
                        disabled={p.notified || busy === p.id}
                        className={cn(
                          'mt-2 inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                          p.notified
                            ? 'border bg-muted text-muted-foreground'
                            : 'bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50',
                        )}
                      >
                        {busy === p.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : p.notified ? (
                          <Check className="h-3 w-3" />
                        ) : null}
                        {p.notified ? 'Sudah dikirim ke jukir' : 'Kirim ke juru parkir'}
                      </button>
                    )}
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>

      {data && data.completed.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Riwayat Kendaraan Keluar</CardTitle>
            <CardDescription>{data.completed.length} sesi parkir terakhir</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 font-medium">Slot</th>
                    <th className="pb-2 font-medium">Kendaraan</th>
                    <th className="pb-2 font-medium">Masuk</th>
                    <th className="pb-2 font-medium">Keluar</th>
                    <th className="pb-2 font-medium">Durasi</th>
                    <th className="pb-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.completed.slice(0, 15).map((s) => (
                    <tr key={s.id} className="border-b last:border-0">
                      <td className="py-2 font-medium">{s.slot_id}</td>
                      <td className="py-2">{s.label}</td>
                      <td className="py-2 tabular">{fmtClock(s.start)}</td>
                      <td className="py-2 tabular">{fmtClock(s.end)}</td>
                      <td className={cn('py-2 font-semibold tabular', s.over_s > 0 && 'text-rose-600 dark:text-rose-400')}>
                        {fmtSmartDuration(s.duration_s)}
                      </td>
                      <td className="py-2">
                        <Badge variant={s.over_s > 0 ? 'danger' : 'success'}>
                          {s.over_s > 0 ? `Lewat +${fmtSmartDuration(s.over_s)}` : 'Tepat batas'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function SlotGrid({
  title,
  desc,
  slots,
  icon: Icon,
  cols,
  emptyText,
}: {
  title: string
  desc: string
  slots: ParkingSlotLive[]
  icon: typeof Car
  cols: string
  emptyText: string
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{desc}</CardDescription>
        </div>
        <div className="hidden gap-3 text-xs text-muted-foreground sm:flex">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />Normal
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-amber-500" />Mendekati
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-rose-500" />Lewat
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {!slots.length ? (
          <p className="py-6 text-center text-sm text-muted-foreground">{emptyText}</p>
        ) : (
          <div className={cn('grid gap-2', cols)}>
            {slots.map((p) => (
              <div key={p.id} className={cn('rounded-lg border-2 p-2 text-xs', levelStyle[p.level])}>
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{p.id}</span>
                  {p.occupied && <Icon className="h-3.5 w-3.5" />}
                </div>
                {p.occupied ? (
                  <>
                    <p className="mt-1 truncate font-medium">{p.label ?? 'Terisi'}</p>
                    <p className={cn('tabular', p.level === 'lewat' && 'font-semibold text-rose-600 dark:text-rose-400')}>
                      {fmtSmartDuration(p.duration_s)}
                    </p>
                  </>
                ) : (
                  <p className="mt-1">Kosong</p>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
