import { useState } from 'react'
import { BellRing } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertRow, alertTypeMeta } from '@/components/AlertRow'
import { alerts as mockAlerts, type AlertItem, type AlertType } from '@/data/mock'
import { fmtClock } from '@/lib/liveSocket'
import { useAlertsLive } from '@/lib/parkingApi'
import { cn } from '@/lib/utils'

export default function Alerts() {
  const [type, setType] = useState<'semua' | AlertType>('semua')
  const [localDone, setLocalDone] = useState<Record<string, boolean>>({})
  const { data, conn, resolveAlert } = useAlertsLive()

  const liveItems: AlertItem[] | null =
    conn === 'live' && data
      ? data.alerts.map((a) => ({
          id: a.id,
          type: a.type,
          severity: a.severity,
          title: a.title,
          description: a.description,
          location: a.location,
          time: fmtClock(a.t),
          camera: a.camera,
          resolved: a.resolved || Boolean(localDone[a.id]),
        }))
      : null

  const allAlerts: AlertItem[] =
    liveItems ?? mockAlerts.map((a) => ({ ...a, resolved: a.resolved || Boolean(localDone[a.id]) }))

  const onResolve = async (id: string) => {
    setLocalDone((prev) => ({ ...prev, [id]: true }))
    if (conn === 'live') {
      try {
        await resolveAlert(id)
      } catch {
        /* tetap tandai secara lokal jika request gagal */
      }
    }
  }

  const types = Object.keys(alertTypeMeta) as AlertType[]
  const list = allAlerts.filter((a) => type === 'semua' || a.type === type)
  const open = list.filter((a) => !a.resolved)
  const done = list.filter((a) => a.resolved)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {types.map((t) => {
          const m = alertTypeMeta[t]
          const count = allAlerts.filter((a) => a.type === t && !a.resolved).length
          return (
            <button
              key={t}
              onClick={() => setType(type === t ? 'semua' : t)}
              className={cn(
                'flex items-center gap-3 rounded-xl border bg-card p-3 text-left transition-colors hover:bg-muted',
                type === t && 'border-primary ring-1 ring-primary',
              )}
            >
              <div className={cn('rounded-lg p-2', m.tone)}>
                <m.icon className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xl font-semibold tabular">{count}</p>
                <p className="text-xs text-muted-foreground">{m.label}</p>
              </div>
            </button>
          )
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Alert Aktif</CardTitle>
            <CardDescription>
              {type === 'semua' ? 'Semua jenis' : alertTypeMeta[type].label} · {open.length} alert
              {conn === 'live' ? ' (Live CV)' : ' (Data contoh)'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {open.length ? (
              open.map((a) => <AlertRow key={a.id} alert={a} showActions onResolve={onResolve} />)
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">Tidak ada alert aktif.</p>
            )}
            {done.length > 0 && (
              <>
                <p className="pt-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Sudah ditangani</p>
                {done.map((a) => <AlertRow key={a.id} alert={a} />)}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BellRing className="h-4 w-4" /> Aturan Alert
            </CardTitle>
            <CardDescription>Ambang batas pemicu notifikasi</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Rule label="Piring tanpa orang" value="5 menit" />
            <Rule label="Makanan/minuman dari luar" value="Langsung" />
            <Rule label="Parkir mobil" value="3 jam (kuning ≥85%)" />
            <Rule label="Parkir motor" value="2 jam (kuning ≥85%)" />
            <Rule label="Waiting time pesanan" value="> target menu" />
            <Rule label="Pengingat reservasi" value="15 menit sebelum" />
            <div className="rounded-lg bg-muted/60 p-3 text-xs text-muted-foreground">
              Notifikasi dikirim real-time ke dashboard dan HP waiter/juru parkir.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Rule({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border p-3">
      <span>{label}</span>
      <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium">{value}</span>
    </div>
  )
}
