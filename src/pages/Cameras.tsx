import { Camera, VideoOff } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cameras } from '@/data/mock'

// Bounding box dummy untuk ilustrasi hasil deteksi
const boxes = [
  { l: 12, t: 30, w: 14, h: 40, label: 'orang 0.94', color: 'border-indigo-400 text-indigo-300' },
  { l: 30, t: 34, w: 13, h: 38, label: 'orang 0.91', color: 'border-indigo-400 text-indigo-300' },
  { l: 22, t: 70, w: 9, h: 10, label: 'piring 0.88', color: 'border-emerald-400 text-emerald-300' },
  { l: 45, t: 66, w: 5, h: 12, label: 'gelas 0.86', color: 'border-sky-400 text-sky-300' },
  { l: 60, t: 62, w: 8, h: 14, label: 'cup luar 0.79', color: 'border-orange-400 text-orange-300' },
]

export default function Cameras() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {cameras.map((c, idx) => (
        <Card key={c.id} className="overflow-hidden">
          <div className="relative aspect-video bg-gradient-to-br from-slate-800 to-slate-950">
            {c.status === 'online' ? (
              <>
                <div className="absolute inset-0 flex items-center justify-center text-slate-600">
                  <Camera className="h-10 w-10" />
                </div>
                {idx % 2 === 0 &&
                  boxes.map((b) => (
                    <div
                      key={b.label}
                      className={`absolute border-2 ${b.color}`}
                      style={{ left: `${b.l}%`, top: `${b.t}%`, width: `${b.w}%`, height: `${b.h}%` }}
                    >
                      <span className="absolute -top-4 left-0 bg-black/60 px-1 text-[9px] whitespace-nowrap">{b.label}</span>
                    </div>
                  ))}
                <span className="absolute top-2 left-2 flex items-center gap-1 rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> LIVE
                </span>
                <span className="absolute top-2 right-2 rounded bg-black/50 px-1.5 py-0.5 text-[10px] text-white tabular">
                  {c.fps} FPS
                </span>
              </>
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-500">
                <VideoOff className="h-8 w-8" />
                <span className="text-xs">Kamera offline</span>
              </div>
            )}
          </div>
          <div className="flex items-center justify-between p-3">
            <div>
              <p className="text-sm font-medium">{c.name}</p>
              <p className="text-xs text-muted-foreground">{c.id}</p>
            </div>
            <div className="flex items-center gap-2">
              {c.status === 'online' && <span className="text-xs text-muted-foreground">{c.detections} objek</span>}
              <Badge variant={c.status === 'online' ? 'success' : 'danger'}>{c.status}</Badge>
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}
