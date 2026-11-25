import { Bot, Cpu, FlaskConical, Send, Sparkles, WifiOff } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { InsightCard } from '@/components/InsightCard'
import { insights as mockInsights, type Insight } from '@/data/mock'
import { useRecommendationsLive } from '@/lib/recommendationsApi'
import { fmtClock } from '@/lib/waitingApi'

const chat = [
  { from: 'user', text: 'Kenapa waiting time naik malam ini?' },
  {
    from: 'ai',
    text: 'Okupansi naik ke 83% sejak 18:00, sementara 2 pesanan grup besar (VIP 2, Meja 4) masuk berdekatan. Rata-rata waiting jadi 21 menit. Saran: prioritaskan VIP 2 dan tambah 1 staf dapur di jam 18–20.',
  },
]

const sourceLabel: Record<string, string> = {
  meja: 'Meja & okupansi',
  waiting_time: 'Waiting time',
  makanan_luar: 'Makanan luar',
  reservasi: 'Reservasi',
  parkir: 'Parkir',
}

const priorityRank = { tinggi: 0, sedang: 1, rendah: 2 } as const

export default function AiInsights() {
  const { data, conn } = useRecommendationsLive()
  const live = data !== null
  // Backend sudah mengurutkan; data contoh diurutkan di sini supaya tampilannya sama.
  const list: (Insight & { mock?: boolean })[] = live
    ? data.recommendations
    : [...mockInsights].sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority])

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-4 bg-gradient-to-r from-indigo-600 to-violet-600 p-6 text-white sm:flex-row sm:items-center">
          <div className="rounded-xl bg-white/15 p-3">
            <Sparkles className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-lg font-semibold">Ringkasan AI{live ? ` · ${fmtClock(data.now)}` : ''}</p>
              {live ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2 py-0.5 text-xs font-medium">
                  <Cpu className="h-3 w-3" />
                  {data.engine === 'rules+llm' ? `Rule engine + LLM (${data.llm.model})` : 'Rule engine'}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2 py-0.5 text-xs font-medium">
                  <WifiOff className="h-3 w-3" /> {conn === 'offline' ? 'Backend offline · contoh mock' : 'Menghubungkan…'}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-white/85">
              {live
                ? data.summary
                : 'Data contoh (mock). Jalankan backend (python -m app.main --source simulate) untuk saran dari data tim.'}
            </p>
            {live && !data.llm.enabled && (
              <p className="mt-1 text-xs text-white/70">Ringkasan LLM tidak aktif ({data.llm.reason}). Saran tetap dari rule engine.</p>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          {live && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-muted-foreground">Sumber data:</span>
              {Object.entries(data.data_sources).map(([k, v]) => (
                <Badge key={k} variant={v === 'mock' ? 'violet' : v === 'tidak_ada' ? 'default' : 'success'}>
                  {sourceLabel[k] ?? k}: {v.replace('_', ' ')}
                </Badge>
              ))}
              <span className="ml-auto text-muted-foreground">
                {data.counts.tinggi} tinggi · {data.counts.sedang} sedang · {data.counts.rendah} rendah
              </span>
            </div>
          )}

          {list.length ? (
            list.map((i) => (
              <Card key={i.id} className="relative p-0">
                {(i.mock || !live) && (
                  <span className="absolute -top-2 right-3 z-10 shadow-sm inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700 dark:bg-violet-500/15 dark:text-violet-300">
                    <FlaskConical className="h-3 w-3" /> mock
                  </span>
                )}
                <InsightCard insight={i} />
              </Card>
            ))
          ) : (
            <Card className="p-8 text-center text-sm text-muted-foreground">Tidak ada tindakan yang perlu dilakukan saat ini.</Card>
          )}
        </div>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Bot className="h-4 w-4" /> Tanya AI</CardTitle>
            <CardDescription>Tanyakan apa saja tentang data restoran hari ini (contoh, belum tersambung)</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col gap-3">
            <div className="flex-1 space-y-3">
              {chat.map((m, idx) => (
                <div
                  key={idx}
                  className={
                    m.from === 'user'
                      ? 'ml-8 rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground'
                      : 'mr-8 rounded-xl rounded-bl-sm bg-muted px-3 py-2 text-sm'
                  }
                >
                  {m.text}
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {['Meja mana yang paling lama?', 'Prediksi ramai besok', 'Rekap alert hari ini'].map((s) => (
                <button key={s} className="rounded-full border px-2.5 py-1 text-xs hover:bg-muted">{s}</button>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                placeholder="Ketik pertanyaan…"
                className="h-9 flex-1 rounded-lg border bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-primary"
              />
              <button className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground" aria-label="Kirim">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
