import { Bot, Send, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { InsightCard } from '@/components/InsightCard'
import { insights } from '@/data/mock'

const chat = [
  { from: 'user', text: 'Kenapa waiting time naik malam ini?' },
  {
    from: 'ai',
    text: 'Okupansi naik ke 83% sejak 18:00, sementara 2 pesanan grup besar (VIP 2, Meja 4) masuk berdekatan. Rata-rata waiting jadi 21 menit. Saran: prioritaskan VIP 2 dan tambah 1 staf dapur di jam 18–20.',
  },
]

export default function AiInsights() {
  return (
    <div className="space-y-6">
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-4 bg-gradient-to-r from-indigo-600 to-violet-600 p-6 text-white sm:flex-row sm:items-center">
          <div className="rounded-xl bg-white/15 p-3">
            <Sparkles className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <p className="text-lg font-semibold">Ringkasan AI · 19:15</p>
            <p className="mt-1 text-sm text-white/85">
              Restoran sedang ramai (83% okupansi). 2 meja perlu dibersihkan, 2 meja segera kosong, dan dapur
              terlambat ±6 menit dari target. Ada 5 rekomendasi aksi, 2 berprioritas tinggi.
            </p>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          {insights.map((i) => (
            <Card key={i.id} className="p-0">
              <InsightCard insight={i} />
            </Card>
          ))}
        </div>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Bot className="h-4 w-4" /> Tanya AI</CardTitle>
            <CardDescription>Tanyakan apa saja tentang data restoran hari ini</CardDescription>
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
