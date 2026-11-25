import { Link } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight, Bell, Car, Clock, Hourglass, Timer, Users } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { StatCard } from '@/components/ui/stat-card'
import { TableCard } from '@/components/TableCard'
import { AlertRow } from '@/components/AlertRow'
import { InsightCard } from '@/components/InsightCard'
import { alerts, insights, occupancyTrend, orders, parkingSlots, tables } from '@/data/mock'

export default function Dashboard() {
  const occupied = tables.filter((t) => t.people > 0).length
  const people = tables.reduce((s, t) => s + t.people, 0)
  const active = orders.filter((o) => o.status !== 'diantar')
  const avgWait = Math.round(active.reduce((s, o) => s + o.waitMin, 0) / active.length)
  const seated = tables.filter((t) => t.durationMin > 0)
  const avgDwell = Math.round(seated.reduce((s, t) => s + t.durationMin, 0) / seated.length)
  const soonFree = tables.filter((t) => t.status === 'segera-kosong').length
  const openAlerts = alerts.filter((a) => !a.resolved)
  const overParking = parkingSlots.filter((p) => p.plate && p.durationMin > p.limitMin).length

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Okupansi Meja" value={`${occupied}/${tables.length}`} hint={`${Math.round((occupied / tables.length) * 100)}% terisi`} icon={Users} />
        <StatCard label="Total Pelanggan" value={`${people}`} hint="terdeteksi kamera" icon={Users} tone="sky" />
        <StatCard label="Rata-rata Waiting" value={`${avgWait}m`} hint="target 15m" icon={Clock} tone="amber" />
        <StatCard label="Rata-rata Lama Duduk" value={`${avgDwell}m`} hint="meja aktif" icon={Timer} tone="violet" />
        <StatCard label="Segera Kosong" value={`${soonFree} meja`} hint="< 10 menit" icon={Hourglass} tone="emerald" />
        <StatCard label="Alert Aktif" value={`${openAlerts.length}`} hint={`${overParking} kendaraan lewat batas`} icon={Bell} tone="rose" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Status Meja Live</CardTitle>
              <CardDescription>Jumlah orang, lama duduk, piring & gelas per meja</CardDescription>
            </div>
            <Link to="/meja" className="flex items-center gap-1 text-sm font-medium text-primary">
              Detail <ArrowRight className="h-4 w-4" />
            </Link>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {tables.map((t) => (
                <TableCard key={t.id} table={t} compact />
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Alert Terbaru</CardTitle>
              <CardDescription>{openAlerts.length} perlu ditangani</CardDescription>
            </div>
            <Link to="/alert" className="flex items-center gap-1 text-sm font-medium text-primary">
              Semua <ArrowRight className="h-4 w-4" />
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {openAlerts.slice(0, 4).map((a) => (
              <AlertRow key={a.id} alert={a} />
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Okupansi Hari Ini</CardTitle>
            <CardDescription>Persentase meja terisi per jam</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={occupancyTrend} margin={{ left: -20, right: 8 }}>
                  <defs>
                    <linearGradient id="occ" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="jam" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                  <YAxis unit="%" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                  <Area type="monotone" dataKey="okupansi" name="Okupansi (%)" stroke="#6366f1" strokeWidth={2} fill="url(#occ)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Rekomendasi AI</CardTitle>
              <CardDescription>Aksi dari data CV</CardDescription>
            </div>
            <Link to="/ai-insight" className="flex items-center gap-1 text-sm font-medium text-primary">
              Semua <ArrowRight className="h-4 w-4" />
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights.slice(0, 3).map((i) => (
              <InsightCard key={i.id} insight={i} compact />
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Parkiran</CardTitle>
            <CardDescription>Kendaraan yang mendekati / melewati batas waktu</CardDescription>
          </div>
          <Link to="/parkir" className="flex items-center gap-1 text-sm font-medium text-primary">
            Detail <ArrowRight className="h-4 w-4" />
          </Link>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {parkingSlots
              .filter((p) => p.plate && p.durationMin / p.limitMin >= 0.85)
              .map((p) => (
                <span
                  key={p.id}
                  className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${
                    p.durationMin > p.limitMin
                      ? 'border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300'
                      : 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300'
                  }`}
                >
                  <Car className="h-4 w-4" />
                  <span className="font-medium">{p.plate}</span>
                  <span className="text-xs opacity-80">
                    {p.id} · {Math.floor(p.durationMin / 60)}j {p.durationMin % 60}m
                  </span>
                </span>
              ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
