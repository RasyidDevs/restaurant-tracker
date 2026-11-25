import { useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  AlertTriangle,
  CheckCheck,
  ChefHat,
  Clock,
  CupSoda,
  Gauge,
  Loader2,
  Target,
  Timer,
  UtensilsCrossed,
  Video,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge, type BadgeVariant } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { StatCard } from '@/components/ui/stat-card'
import { SourceBar } from '@/components/SourceBar'
import { fmtClock, fmtDuration, useWaitingLive, type WaitingSession } from '@/lib/waitingApi'
import { cn } from '@/lib/utils'

const statusMeta: Record<WaitingSession['status'], { label: string; variant: BadgeVariant }> = {
  menunggu: { label: 'Belum ada sajian', variant: 'warning' },
  sebagian: { label: 'Sebagian tersaji', variant: 'primary' },
  lengkap: { label: 'Lengkap', variant: 'success' },
  pergi: { label: 'Pelanggan pergi', variant: 'danger' },
}

const reasonLabel: Record<NonNullable<WaitingSession['end_reason']>, string> = {
  otomatis: 'Otomatis (CV)',
  konfirmasi_waiter: 'Konfirmasi waiter',
  pelanggan_pergi: 'Pelanggan pergi',
}

export default function WaitingTime() {
  const { data, conn, confirm } = useWaitingLive()
  const [busy, setBusy] = useState<string | null>(null)

  const onConfirm = async (id: string) => {
    setBusy(id)
    try {
      await confirm(id)
    } finally {
      setBusy(null)
    }
  }

  const tableName = (id: string) => data?.tables.find((t) => t.id === id)?.name ?? id
  const target = (data?.rules.target_min ?? 20) * 60

  return (
    <div className="space-y-6">
      <SourceBar source={data?.source} now={data?.now} conn={conn} />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Sedang Menunggu" value={`${data?.active.length ?? 0} meja`} icon={ChefHat} />
        <StatCard label="Rata-rata Waiting" value={fmtDuration(data?.stats.avg_wait_s)} hint={`target ${data?.rules.target_min ?? 20} menit`} icon={Clock} tone="amber" />
        <StatCard label="Median Waiting" value={fmtDuration(data?.stats.median_wait_s)} hint={`terlama ${fmtDuration(data?.stats.max_wait_s)}`} icon={Gauge} tone="violet" />
        <StatCard label="Minuman Pertama" value={fmtDuration(data?.stats.avg_first_drink_s)} hint="rata-rata sejak duduk" icon={CupSoda} tone="sky" />
        <StatCard label="Makanan Pertama" value={fmtDuration(data?.stats.avg_first_food_s)} hint="rata-rata sejak duduk" icon={UtensilsCrossed} tone="emerald" />
        <StatCard
          label="Sesuai Target"
          value={data?.stats.on_target_pct != null ? `${data.stats.on_target_pct}%` : '–'}
          hint={`${data?.stats.count ?? 0} sesi selesai`}
          icon={Target}
          tone="rose"
        />
      </div>

      {/* Sesi berjalan */}
      <Card>
        <CardHeader>
          <CardTitle>Meja Sedang Menunggu</CardTitle>
          <CardDescription>
            Timer mulai saat pelanggan terdeteksi duduk, berhenti saat piring & gelas baru ≥ jumlah orang (waktu item terakhir tiba)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!data?.active.length ? (
            <Empty text={conn === 'offline' ? 'Backend belum terhubung.' : 'Tidak ada meja yang sedang menunggu.'} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 font-medium">Meja</th>
                    <th className="pb-2 font-medium">Orang</th>
                    <th className="pb-2 font-medium">Duduk</th>
                    <th className="pb-2 font-medium">Waiting</th>
                    <th className="pb-2 font-medium">Minuman</th>
                    <th className="pb-2 font-medium">Makanan</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {[...data.active]
                    .sort((a, b) => b.waiting_s - a.waiting_s)
                    .map((s) => {
                      const pct = (s.waiting_s / target) * 100
                      const over = s.waiting_s > target
                      return (
                        <tr key={s.id} className="border-b align-top last:border-0">
                          <td className="py-3">
                            <p className="font-medium">{tableName(s.table_id)}</p>
                            <p className="text-xs text-muted-foreground">{s.id}</p>
                          </td>
                          <td className="py-3 tabular">{s.people_peak}</td>
                          <td className="py-3 tabular">{fmtClock(s.start)}</td>
                          <td className="w-40 py-3">
                            <div className="flex items-baseline justify-between">
                              <span className={cn('text-base font-semibold tabular', over && 'text-rose-600 dark:text-rose-400')}>
                                {fmtDuration(s.waiting_s)}
                              </span>
                              <span className="text-xs text-muted-foreground">/ {fmtDuration(target)}</span>
                            </div>
                            <Progress
                              value={pct}
                              className="mt-1"
                              barClassName={over ? 'bg-rose-500' : pct > 75 ? 'bg-amber-500' : 'bg-indigo-500'}
                            />
                          </td>
                          <td className="py-3">
                            <ItemCell served={s.glasses_served} need={s.required_glasses} firstAt={s.first_drink_s} />
                          </td>
                          <td className="py-3">
                            <ItemCell served={s.plates_served} need={s.people_peak} firstAt={s.first_food_s} />
                          </td>
                          <td className="py-3">
                            <Badge variant={statusMeta[s.status].variant}>{statusMeta[s.status].label}</Badge>
                            {s.alerts.map((a) => (
                              <p key={a.kind} className="mt-1 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                                <AlertTriangle className="h-3 w-3" />
                                {a.kind === 'belum_lengkap' ? 'Belum lengkap' : 'Belum disajikan'}
                              </p>
                            ))}
                          </td>
                          <td className="py-3 text-right">
                            <button
                              onClick={() => onConfirm(s.id)}
                              disabled={busy === s.id}
                              className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
                              title="Tandai lengkap, mis. satu piring untuk berdua. Waktu selesai = item terakhir tiba."
                            >
                              {busy === s.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCheck className="h-3 w-3" />}
                              Sudah lengkap
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-3">
        {/* Grafik per jam */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Rata-rata Waiting per Jam</CardTitle>
            <CardDescription>Dari sesi yang sudah lengkap tersaji</CardDescription>
          </CardHeader>
          <CardContent>
            {data?.stats.by_hour.length ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={data.stats.by_hour.map((h) => ({ ...h, target: data.rules.target_min }))}
                    margin={{ left: -20, right: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="jam" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                    <YAxis unit="m" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="rata_menit" name="Rata-rata (menit)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    <Line dataKey="target" name="Target" stroke="#94a3b8" strokeDasharray="5 5" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <Empty text="Belum ada sesi yang selesai." />
            )}
          </CardContent>
        </Card>

        {/* Alert waiting */}
        <Card>
          <CardHeader>
            <CardTitle>Alert Waiting Time</CardTitle>
            <CardDescription>
              Belum ada sajian &gt; {data?.rules.alert_no_item_min ?? 20}m · belum lengkap &gt; {data?.rules.alert_partial_min ?? 25}m
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {data?.alerts.length ? (
              data.alerts.slice(0, 6).map((a, i) => (
                <div key={i} className="flex gap-3 rounded-lg border p-3">
                  <div className="h-fit rounded-lg bg-amber-100 p-2 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300">
                    <Timer className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm">{a.message}</p>
                    <p className="text-xs text-muted-foreground">{fmtClock(a.t)}</p>
                  </div>
                </div>
              ))
            ) : (
              <Empty text="Tidak ada alert." />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Riwayat */}
      <Card>
        <CardHeader>
          <CardTitle>Riwayat Sesi</CardTitle>
          <CardDescription>
            {data?.stats.count ?? 0} lengkap · {data?.stats.left_count ?? 0} pelanggan pergi sebelum lengkap
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!data?.completed.length ? (
            <Empty text="Belum ada riwayat." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 font-medium">Meja</th>
                    <th className="pb-2 font-medium">Orang</th>
                    <th className="pb-2 font-medium">Duduk</th>
                    <th className="pb-2 font-medium">Selesai</th>
                    <th className="pb-2 font-medium">Minuman 1</th>
                    <th className="pb-2 font-medium">Makanan 1</th>
                    <th className="pb-2 font-medium">Waiting</th>
                    <th className="pb-2 font-medium">Cara selesai</th>
                  </tr>
                </thead>
                <tbody>
                  {data.completed.map((s) => (
                    <tr key={s.id} className="border-b last:border-0">
                      <td className="py-2.5 font-medium">{tableName(s.table_id)}</td>
                      <td className="py-2.5 tabular">{s.people_peak}</td>
                      <td className="py-2.5 tabular">{fmtClock(s.start)}</td>
                      <td className="py-2.5 tabular">{fmtClock(s.end)}</td>
                      <td className="py-2.5 tabular">{fmtDuration(s.first_drink_s)}</td>
                      <td className="py-2.5 tabular">{fmtDuration(s.first_food_s)}</td>
                      <td
                        className={cn(
                          'py-2.5 font-semibold tabular',
                          s.status === 'lengkap' && s.waiting_s > s.target_s && 'text-rose-600 dark:text-rose-400',
                        )}
                      >
                        {fmtDuration(s.waiting_s)}
                      </td>
                      <td className="py-2.5">
                        <Badge variant={s.status === 'pergi' ? 'danger' : s.end_reason === 'otomatis' ? 'success' : 'info'}>
                          {s.end_reason ? reasonLabel[s.end_reason] : '–'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Kamera beranotasi (hanya untuk sumber video asli) */}
      {conn === 'live' &&
        data &&
        !data.source.detail.startsWith('Mode simulasi') &&
        (data.source.state === 'running' || data.source.state === 'finished') && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Video className="h-4 w-4" /> Kamera & Deteksi
              </CardTitle>
              <CardDescription>Zona meja, kotak deteksi orang/piring/gelas, dan timer per meja</CardDescription>
            </CardHeader>
            <CardContent>
              <img src="/api/stream.mjpg" alt="Stream kamera beranotasi" className="w-full rounded-lg bg-slate-900" />
            </CardContent>
          </Card>
        )}
    </div>
  )
}

function ItemCell({ served, need, firstAt }: { served: number; need: number; firstAt: number | null }) {
  const ok = need > 0 ? served >= need : served > 0
  return (
    <div>
      <span className={cn('font-semibold tabular', ok ? 'text-emerald-600 dark:text-emerald-400' : '')}>
        {served}
        {need > 0 && <span className="font-normal text-muted-foreground">/{need}</span>}
      </span>
      <p className="text-xs text-muted-foreground">{firstAt != null ? `pertama ${fmtDuration(firstAt)}` : 'belum'}</p>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{text}</p>
}
