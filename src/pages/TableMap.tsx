import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Armchair, CalendarClock, Camera, Clock, CupSoda, Hourglass, Loader2, PackageX, Plus, Timer, Users, UtensilsCrossed, WifiOff } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { StatCard } from '@/components/ui/stat-card'
import { TableCard } from '@/components/TableCard'
import { dwellDistribution as mockDwell, tables as mockTables, tableStatusMeta, type TableStatus } from '@/data/mock'
import { toDiningTable, useOccupancyLive, type OccupancySnapshot } from '@/lib/occupancyApi'
import { fmtClock, fmtDuration } from '@/lib/waitingApi'
import { cn, formatMinutes } from '@/lib/utils'

const filters: { key: 'semua' | TableStatus; label: string }[] = [
  { key: 'semua', label: 'Semua' },
  { key: 'kosong', label: 'Kosong' },
  { key: 'terisi', label: 'Terisi' },
  { key: 'segera-kosong', label: 'Segera Kosong' },
  { key: 'reserved', label: 'Reserved' },
  { key: 'perlu-dibersihkan', label: 'Perlu Dibersihkan' },
]

export default function TableMap() {
  const [filter, setFilter] = useState<'semua' | TableStatus>('semua')
  const [selectedId, setSelectedId] = useState('T1')
  const { data, conn } = useOccupancyLive()
  // Data asli dari backend CV kalau terhubung; kalau belum, tampilkan data contoh.
  const live = conn === 'live' && data != null
  const tables = live ? data.tables.map(toDiningTable) : mockTables
  const selected = tables.find((t) => t.id === selectedId) ?? tables[0]

  const list = tables.filter((t) => filter === 'semua' || t.status === filter)
  const groups = live
    ? [{ label: 'Area kamera', items: list }]
    : (['Indoor', 'Outdoor', 'VIP'] as const).map((zone) => ({ label: zone, items: list.filter((t) => t.zone === zone) }))
  const people = tables.reduce((s, t) => s + t.people, 0)
  const seats = tables.reduce((s, t) => s + t.seats, 0)
  const seated = tables.filter((t) => t.durationMin > 0)
  const soonFree = tables
    .filter((t) => t.estFreeMin !== undefined)
    .sort((a, b) => a.estFreeMin! - b.estFreeMin!)
  const reserved = mockTables.filter((t) => t.status === 'reserved') // fitur reservasi (Micheal), masih data contoh
  const distribution = live ? data.stats.distribution : mockDwell

  const ratio = (n: number) => (selected.people ? n / selected.people : 0)

  if (!selected) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Belum ada meja di konfigurasi backend.</p>
  }

  return (
    <div className="space-y-6">
      <SourceBar data={data} conn={conn} />

      {/* Ringkasan okupansi */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label="Orang di Meja"
          value={`${people}`}
          hint={`${tables.filter((t) => t.people > 0).length}/${tables.length} meja terisi`}
          icon={Users}
        />
        <StatCard
          label="Kursi Terpakai"
          value={`${Math.round((100 * people) / Math.max(1, seats))}%`}
          hint={`${people} dari ${seats} kursi`}
          icon={Armchair}
          tone="violet"
        />
        <StatCard
          label="Rata-rata Lama Duduk"
          value={
            live
              ? fmtDuration(data.stats.avg_dwell_s)
              : formatMinutes(Math.round(seated.reduce((s, t) => s + t.durationMin, 0) / Math.max(1, seated.length)))
          }
          hint={live ? `${data.stats.count} kunjungan selesai` : 'meja yang sedang terisi'}
          icon={Timer}
          tone="sky"
        />
        <StatCard
          label="Segera Kosong"
          value={`${tables.filter((t) => t.status === 'segera-kosong').length} meja`}
          hint={soonFree[0] ? `tercepat ${soonFree[0].name} ±${soonFree[0].estFreeMin}m` : 'belum ada estimasi'}
          icon={Hourglass}
          tone="amber"
        />
      </div>

      {/* Filter & legend */}
      <div className="flex flex-wrap items-center gap-2">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              'flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors',
              filter === f.key ? 'border-primary bg-accent text-primary' : 'bg-card hover:bg-muted',
            )}
          >
            {f.key !== 'semua' && <span className={cn('h-2 w-2 rounded-full', tableStatusMeta[f.key].dot)} />}
            {f.label}
            <span className="text-xs text-muted-foreground">
              {f.key === 'semua' ? tables.length : tables.filter((t) => t.status === f.key).length}
            </span>
          </button>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        {/* Denah */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Denah Restoran</CardTitle>
            <CardDescription>Klik meja untuk melihat detail deteksi</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {!list.length && <p className="py-6 text-center text-sm text-muted-foreground">Tidak ada meja dengan status ini.</p>}
            {groups.map(({ label, items: zt }) => {
              if (!zt.length) return null
              return (
                <div key={label}>
                  <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                    {zt.map((t) => (
                      <TableCard key={t.id} table={t} selected={t.id === selectedId} onClick={() => setSelectedId(t.id)} />
                    ))}
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>

        {/* Detail meja */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{selected.name}</CardTitle>
              <Badge variant="primary">{tableStatusMeta[selected.status].label}</Badge>
            </div>
            <CardDescription>
              {live ? 'Kamera' : `Zona ${selected.zone}`} · {selected.seats} kursi{selected.phase && ` · ${selected.phase}`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex aspect-video items-center justify-center rounded-lg bg-slate-900 text-slate-400">
              <div className="flex flex-col items-center gap-1 text-xs">
                <Camera className="h-6 w-6" /> Snapshot kamera meja
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Metric icon={Users} label="Jumlah orang" value={`${selected.people} / ${selected.seats}`} />
              <Metric icon={Clock} label="Lama di meja" value={selected.durationMin ? formatMinutes(selected.durationMin) : '-'} />
              <Metric icon={UtensilsCrossed} label="Piring" value={`${selected.plates}`} />
              <Metric icon={CupSoda} label="Gelas" value={`${selected.glasses}`} />
            </div>

            {/* #5 Orang vs piring & gelas */}
            <div className="rounded-lg border p-3">
              <p className="text-sm font-medium">Rasio Orang : Piring : Gelas</p>
              <div className="mt-3 space-y-2 text-xs">
                <div>
                  <div className="mb-1 flex justify-between"><span>Piring per orang</span><span className="tabular">{ratio(selected.plates).toFixed(1)}</span></div>
                  <Progress value={ratio(selected.plates) * 100} barClassName={ratio(selected.plates) < 1 ? 'bg-amber-500' : 'bg-emerald-500'} />
                </div>
                <div>
                  <div className="mb-1 flex justify-between"><span>Gelas per orang</span><span className="tabular">{ratio(selected.glasses).toFixed(1)}</span></div>
                  <Progress value={ratio(selected.glasses) * 100} barClassName={ratio(selected.glasses) < 1 ? 'bg-amber-500' : 'bg-emerald-500'} />
                </div>
              </div>
              {selected.people > 0 && selected.plates < selected.people && (
                <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                  {selected.people - selected.plates} orang belum memesan makanan, peluang upsell.
                </p>
              )}
            </div>

            {selected.estFreeMin !== undefined && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-500/40 dark:bg-amber-500/10">
                <p className="flex items-center gap-1.5 text-sm font-medium text-amber-800 dark:text-amber-300">
                  <Hourglass className="h-4 w-4" /> Estimasi kosong ±{selected.estFreeMin} menit
                </p>
                <Progress value={selected.estFreeConfidence ?? 0} className="mt-2 bg-amber-200/60 dark:bg-amber-500/20" barClassName="bg-amber-500" />
                <p className="mt-1 text-xs text-muted-foreground">Confidence {selected.estFreeConfidence}%</p>
                {selected.estFreeReason && <p className="mt-1 text-xs text-muted-foreground">{selected.estFreeReason}</p>}
              </div>
            )}
            {selected.outsideFood && (
              <div className="flex items-start gap-2 rounded-lg border border-orange-300 bg-orange-50 p-3 text-sm text-orange-800 dark:border-orange-500/40 dark:bg-orange-500/10 dark:text-orange-300">
                <PackageX className="mt-0.5 h-4 w-4 shrink-0" /> Terdeteksi makanan/minuman dari luar
              </div>
            )}
            {selected.idleDishesMin !== undefined && (
              <div className="flex items-start gap-2 rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> Piring tanpa orang selama {selected.idleDishesMin} menit
              </div>
            )}
            {selected.status === 'reserved' && (
              <div className="flex items-start gap-2 rounded-lg border border-violet-300 bg-violet-50 p-3 text-sm text-violet-700 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-300">
                <CalendarClock className="mt-0.5 h-4 w-4 shrink-0" /> Reserved untuk {selected.reservedFor} pukul {selected.reservedAt}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* #7 Estimasi segera kosong */}
        <Card>
          <CardHeader>
            <CardTitle>Estimasi Bangku Segera Kosong</CardTitle>
            <CardDescription>
              {live
                ? `Dari fase makan & riwayat ${data.learned.samples} kunjungan${data.learned.post_food_s ? '' : ' (masih pakai angka default)'}`
                : 'Diprediksi dari lama duduk, sisa makanan & gerakan'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!soonFree.length && <p className="py-4 text-center text-sm text-muted-foreground">Belum ada meja terisi.</p>}
            {soonFree.map((t) => (
              <div key={t.id}>
                <div className="flex items-center gap-3">
                  <div className="w-16 text-sm font-medium">{t.name}</div>
                  <div className="flex-1">
                    <Progress value={100 - (t.estFreeMin! / 45) * 100} barClassName={t.estFreeMin! <= 10 ? 'bg-amber-500' : 'bg-indigo-500'} />
                  </div>
                  <div className="w-20 text-right text-sm tabular">±{t.estFreeMin}m</div>
                </div>
                {t.estFreeReason && (
                  <p className="mt-0.5 pl-19 text-xs text-muted-foreground">
                    {t.estFreeReason} · {t.estFreeConfidence}%
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        {/* #3 Reserved */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Reserved Table</CardTitle>
              <CardDescription>Reservasi hari ini</CardDescription>
            </div>
            <Button size="sm" variant="outline"><Plus className="h-3.5 w-3.5" /> Tambah</Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {reserved.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">{t.reservedFor}</p>
                  <p className="text-xs text-muted-foreground">{t.name} · {t.seats} kursi</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold tabular">{t.reservedAt}</p>
                  <Badge variant="success">meja kosong</Badge>
                </div>
              </div>
            ))}
            <div className="flex items-center justify-between rounded-lg border border-dashed p-3 opacity-70">
              <div>
                <p className="text-sm font-medium">Kel. Budi</p>
                <p className="text-xs text-muted-foreground">Meja 7 · 4 kursi</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold tabular">21:00</p>
                <Badge variant="warning">masih terisi</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* #2 Distribusi lama duduk */}
        <Card>
          <CardHeader>
            <CardTitle>Distribusi Lama di Meja</CardTitle>
            <CardDescription>{live ? `Kunjungan tercatat backend (${data.stats.count})` : 'Jumlah kunjungan hari ini'}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distribution} margin={{ left: -25, right: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="rentang" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: 'var(--muted)' }} contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="meja" name="Kunjungan" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Metric({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/60 p-3">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" /> {label}
      </p>
      <p className="mt-1 text-lg font-semibold tabular">{value}</p>
    </div>
  )
}

function SourceBar({ data, conn }: { data: OccupancySnapshot | null; conn: string }) {
  if (conn !== 'live' || !data) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
        {conn === 'offline' ? <WifiOff className="mt-0.5 h-4 w-4 shrink-0" /> : <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />}
        <div>
          <p className="font-medium">{conn === 'offline' ? 'Backend CV belum terhubung, menampilkan data contoh' : 'Menghubungkan ke backend…'}</p>
          {conn === 'offline' && (
            <p className="mt-1">
              Jalankan di folder <code className="rounded bg-black/5 px-1 dark:bg-white/10">backend</code>:{' '}
              <code className="rounded bg-black/5 px-1 dark:bg-white/10">.venv\Scripts\python -m app.main</code>
            </p>
          )}
        </div>
      </div>
    )
  }
  const tone = data.source.state === 'running' ? 'bg-emerald-500' : data.source.state === 'error' ? 'bg-rose-500' : 'bg-amber-500'
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-sm">
      <span className={cn('h-2 w-2 rounded-full', tone, data.source.state === 'running' && 'animate-pulse')} />
      <span className="font-medium capitalize">{data.source.state}</span>
      <span className="text-muted-foreground">· {data.source.detail}</span>
      <span className="ml-auto text-xs text-muted-foreground tabular">waktu sumber {fmtClock(data.now)}</span>
    </div>
  )
}
