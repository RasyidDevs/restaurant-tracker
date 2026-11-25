import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { CheckCircle2, ChefHat, Clock, Timer, TriangleAlert } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge, type BadgeVariant } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { StatCard } from '@/components/ui/stat-card'
import { orders, waitingTrend, type OrderStatus } from '@/data/mock'
import { cn } from '@/lib/utils'

const statusMeta: Record<OrderStatus, { label: string; variant: BadgeVariant }> = {
  menunggu: { label: 'Menunggu', variant: 'warning' },
  dimasak: { label: 'Dimasak', variant: 'primary' },
  diantar: { label: 'Sudah diantar', variant: 'success' },
}

export default function WaitingTime() {
  const active = orders.filter((o) => o.status !== 'diantar')
  const late = active.filter((o) => o.waitMin > o.targetMin)
  const avg = Math.round(active.reduce((s, o) => s + o.waitMin, 0) / active.length)
  const longest = Math.max(...active.map((o) => o.waitMin))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Pesanan Aktif" value={`${active.length}`} icon={ChefHat} />
        <StatCard label="Rata-rata Waiting" value={`${avg}m`} hint="target 15m" icon={Clock} tone="amber" />
        <StatCard label="Waiting Terlama" value={`${longest}m`} hint="VIP 2" icon={Timer} tone="rose" />
        <StatCard label="Melewati Target" value={`${late.length}`} hint="pesanan" icon={TriangleAlert} tone="rose" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pesanan Berjalan</CardTitle>
          <CardDescription>
            Timer dimulai saat CV mendeteksi pelanggan selesai memesan, berhenti saat makanan tiba di meja
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 font-medium">Pesanan</th>
                  <th className="pb-2 font-medium">Meja</th>
                  <th className="pb-2 font-medium">Item</th>
                  <th className="pb-2 font-medium">Dipesan</th>
                  <th className="pb-2 font-medium">Waiting</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const pct = (o.waitMin / o.targetMin) * 100
                  const over = o.waitMin > o.targetMin
                  return (
                    <tr key={o.id} className="border-b last:border-0">
                      <td className="py-3 font-medium">{o.id}</td>
                      <td className="py-3">{o.table}</td>
                      <td className="py-3 text-muted-foreground">{o.items.join(', ')}</td>
                      <td className="py-3 tabular">{o.orderedAt}</td>
                      <td className="w-44 py-3">
                        <div className="flex items-center justify-between text-xs">
                          <span className={cn('font-semibold tabular', over && o.status !== 'diantar' && 'text-rose-600 dark:text-rose-400')}>
                            {o.waitMin}m
                          </span>
                          <span className="text-muted-foreground">/ {o.targetMin}m</span>
                        </div>
                        <Progress
                          value={pct}
                          className="mt-1"
                          barClassName={
                            o.status === 'diantar' ? 'bg-emerald-500' : over ? 'bg-rose-500' : pct > 75 ? 'bg-amber-500' : 'bg-indigo-500'
                          }
                        />
                      </td>
                      <td className="py-3">
                        <Badge variant={statusMeta[o.status].variant}>
                          {o.status === 'diantar' && <CheckCircle2 className="h-3 w-3" />}
                          {statusMeta[o.status].label}
                        </Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tren Waiting Time</CardTitle>
          <CardDescription>Rata-rata menit tunggu per jam dibanding target</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={waitingTrend} margin={{ left: -20, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="jam" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                <YAxis unit="m" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="rata" name="Rata-rata" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="target" name="Target" stroke="#94a3b8" strokeDasharray="5 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
