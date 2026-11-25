import { useState } from 'react'
import { CheckCheck, CupSoda, FlaskConical, Loader2, PackageX, ShieldCheck, SlidersHorizontal, WifiOff } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { StatCard } from '@/components/ui/stat-card'
import { useOutsideFoodLive, type OutsideFoodAlert, type OutsideFoodRules } from '@/lib/outsideFoodApi'
import { fmtClock, fmtDuration } from '@/lib/waitingApi'
import { cn } from '@/lib/utils'

const endLabel: Record<NonNullable<OutsideFoodAlert['end_reason']>, string> = {
  objek_hilang: 'Objek hilang',
  ditangani_staf: 'Ditangani staf',
}

export default function OutsideFood() {
  const { data, conn, resolve } = useOutsideFoodLive()
  const [busy, setBusy] = useState<string | null>(null)

  const onResolve = async (id: string) => {
    setBusy(id)
    try {
      await resolve(id)
    } finally {
      setBusy(null)
    }
  }

  const isMock = data?.source === 'mock'

  return (
    <div className="space-y-6">
      {conn !== 'live' && !data ? (
        <div className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
          {conn === 'offline' ? <WifiOff className="mt-0.5 h-4 w-4 shrink-0" /> : <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />}
          <div>
            <p className="font-medium">{conn === 'offline' ? 'Backend CV belum terhubung' : 'Menghubungkan ke backend…'}</p>
            {conn === 'offline' && (
              <p className="mt-1">
                Jalankan di folder <code className="rounded bg-black/5 px-1 dark:bg-white/10">backend</code>:{' '}
                <code className="rounded bg-black/5 px-1 dark:bg-white/10">.venv\Scripts\python -m app.main --source simulate</code>
              </p>
            )}
          </div>
        </div>
      ) : (
        isMock && (
          <div className="flex items-start gap-3 rounded-xl border border-violet-300 bg-violet-50 p-3 text-sm text-violet-900 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-200">
            <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              <span className="font-medium">Data MOCK.</span> Deteksi di halaman ini berasal dari generator simulasi, bukan model
              kamera. Aturan anti false alarm tetap sama seperti untuk deteksi asli.
            </p>
          </div>
        )
      )}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Alert Aktif" value={`${data?.stats.active_count ?? 0}`} hint="meja perlu dicek" icon={PackageX} tone="amber" />
        <StatCard label="Total Terdeteksi" value={`${data?.stats.total_count ?? 0}`} hint="sejak server berjalan" icon={CupSoda} tone="sky" />
        <StatCard label="Ditangani Staf" value={`${data?.stats.handled_count ?? 0}`} hint="ditandai manual" icon={ShieldCheck} tone="emerald" />
        <StatCard
          label="Sumber Deteksi"
          value={data ? (isMock ? 'MOCK' : 'Kamera') : '–'}
          hint={data?.source_status.detail}
          icon={FlaskConical}
          tone="violet"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Meja Terindikasi Membawa Makanan/Minuman dari Luar</CardTitle>
            <CardDescription>Objek terdeteksi konsisten di meja. Cek langsung sebelum menegur pelanggan, karena deteksi bisa keliru.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {data?.active.length ? (
              data.active.map((a) => (
                <AlertItem key={a.id} a={a} now={data.now} busy={busy === a.id} onResolve={() => onResolve(a.id)} />
              ))
            ) : (
              <Empty text={conn === 'offline' ? 'Backend belum terhubung.' : 'Tidak ada indikasi saat ini.'} />
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Status Meja</CardTitle>
              <CardDescription>Oranye = ada alert aktif</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-2">
                {data?.tables.map((t) => (
                  <div
                    key={t.id}
                    className={cn(
                      'rounded-lg border p-2 text-center text-xs',
                      t.flagged && 'border-orange-400 bg-orange-50 text-orange-700 dark:bg-orange-500/10 dark:text-orange-300',
                    )}
                  >
                    <p className="font-semibold">{t.name}</p>
                    <p className="text-muted-foreground">{t.people} orang</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {data && <RulesCard rules={data.rules} />}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Riwayat</CardTitle>
          <CardDescription>Alert yang sudah selesai</CardDescription>
        </CardHeader>
        <CardContent>
          {!data?.history.length ? (
            <Empty text="Belum ada riwayat." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2 font-medium">Meja</th>
                    <th className="pb-2 font-medium">Objek</th>
                    <th className="pb-2 font-medium">Confidence</th>
                    <th className="pb-2 font-medium">Terlihat</th>
                    <th className="pb-2 font-medium">Durasi</th>
                    <th className="pb-2 font-medium">Selesai</th>
                  </tr>
                </thead>
                <tbody>
                  {data.history.map((a) => (
                    <tr key={a.id} className="border-b last:border-0">
                      <td className="py-2.5 font-medium">{a.table_name}</td>
                      <td className="py-2.5">
                        {a.label} {a.source === 'mock' && <Badge variant="violet">mock</Badge>}
                      </td>
                      <td className="py-2.5 tabular">{Math.round(a.confidence * 100)}%</td>
                      <td className="py-2.5 tabular">{fmtClock(a.first_seen)}</td>
                      <td className="py-2.5 tabular">{fmtDuration((a.ended_at ?? a.last_seen) - a.first_seen)}</td>
                      <td className="py-2.5">
                        <Badge variant={a.end_reason === 'ditangani_staf' ? 'success' : 'default'}>
                          {a.end_reason ? endLabel[a.end_reason] : '–'}
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
    </div>
  )
}

function AlertItem({ a, now, busy, onResolve }: { a: OutsideFoodAlert; now: number; busy: boolean; onResolve: () => void }) {
  const pct = Math.round(a.confidence * 100)
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-l-4 border-l-orange-500 p-3 sm:flex-row sm:items-center">
      <div className="h-fit w-fit rounded-lg bg-orange-100 p-2 text-orange-600 dark:bg-orange-500/15 dark:text-orange-300">
        {a.category === 'minuman' ? <CupSoda className="h-4 w-4" /> : <PackageX className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium">{a.table_name}</p>
          <span className="text-sm text-muted-foreground">· {a.label}</span>
          <Badge variant={a.category === 'minuman' ? 'info' : 'warning'}>{a.category}</Badge>
          {a.source === 'mock' && <Badge variant="violet">mock</Badge>}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Progress value={pct} className="max-w-40" barClassName={pct >= 70 ? 'bg-orange-500' : 'bg-amber-400'} />
          <span className="text-xs tabular text-muted-foreground">
            confidence {pct}% (maks {Math.round(a.max_confidence * 100)}%)
          </span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Pertama terlihat {fmtClock(a.first_seen)} · sudah {fmtDuration(now - a.first_seen)} · alert {fmtClock(a.t)}
        </p>
      </div>
      <button
        onClick={onResolve}
        disabled={busy}
        className="inline-flex items-center gap-1 self-start rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50 sm:self-center"
      >
        {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCheck className="h-3 w-3" />}
        Sudah ditangani
      </button>
    </div>
  )
}

function RulesCard({ rules }: { rules: OutsideFoodRules }) {
  const rows: [string, string][] = [
    ['Confidence minimum', `${Math.round(rules.conf_threshold * 100)}%`],
    ['Harus terlihat', `${rules.min_persist_s} detik`],
    ['Konsistensi frame', `≥ ${Math.round(rules.min_hit_ratio * 100)}%`],
    ['Selesai jika hilang', `${rules.clear_after_s} detik`],
    ['Jeda alert ulang', `${Math.round(rules.cooldown_s / 60)} menit`],
    ['Hanya meja berpenghuni', rules.require_occupied ? 'Ya' : 'Tidak'],
  ]
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4" /> Aturan Deteksi
        </CardTitle>
        <CardDescription>
          Ubah di <code className="text-xs">config.json → features.outside_food</code>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2">
            <span>{k}</span>
            <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium">{v}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{text}</p>
}
