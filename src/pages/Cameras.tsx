import { Camera, Loader2, Video, VideoOff } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SourceBar } from '@/components/SourceBar'
import { cameras } from '@/data/mock'
import { useParkingLive } from '@/lib/parkingApi'
import { useWaitingLive } from '@/lib/waitingApi'
import type { SourceInfo } from '@/lib/liveSocket'

export default function Cameras() {
  const { data: waiting, conn: waitConn } = useWaitingLive()
  const { data: parking, conn: parkConn } = useParkingLive()

  const indoorLive = waitConn === 'live' && waiting && !waiting.source.detail.startsWith('Mode simulasi')
  const parkingLive =
    parkConn === 'live' &&
    parking &&
    parking.source.state !== 'idle' &&
    !parking.source.detail.startsWith('Mode simulasi')

  return (
    <div className="space-y-6">
      <SourceBar source={parking?.source ?? waiting?.source} now={parking?.now ?? waiting?.now} conn={parkConn} />

      {/* 2 Video Demo Asli (Meja & Parkiran) */}
      <div className="grid gap-4 lg:grid-cols-2">
        <LiveCameraCard
          id="CAM-01"
          name="Area Meja Restoran"
          streamUrl="/api/stream.mjpg"
          source={waiting?.source}
          isVideo={Boolean(indoorLive)}
          summary={
            waiting
              ? `${waiting.tables.reduce((s, t) => s + t.people, 0)} orang · ${waiting.tables.length} zona meja`
              : undefined
          }
        />
        <LiveCameraCard
          id="CAM-P1"
          name="Area Parkiran"
          streamUrl="/api/parking/stream.mjpg"
          source={parking?.source}
          isVideo={Boolean(parkingLive)}
          summary={
            parking
              ? `${parking.stats.car_occupied} mobil · ${parking.stats.bike_occupied} motor · ${parking.stats.over_count} lewat batas`
              : undefined
          }
        />
      </div>

      {/* Kamera tambahan lainnya (ilustrasi multi-zona) */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cameras
          .filter((c) => c.id !== 'CAM-01' && c.id !== 'CAM-P1')
          .map((c) => (
            <Card key={c.id} className="overflow-hidden">
              <div className="relative aspect-video bg-gradient-to-br from-slate-800 to-slate-950">
                {c.status === 'online' ? (
                  <>
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-slate-500">
                      <Camera className="h-8 w-8" />
                      <span className="text-[11px]">Simulasi multi-kamera</span>
                    </div>
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
                <Badge variant={c.status === 'online' ? 'default' : 'danger'}>{c.status}</Badge>
              </div>
            </Card>
          ))}
      </div>
    </div>
  )
}

function LiveCameraCard({
  id,
  name,
  streamUrl,
  source,
  isVideo,
  summary,
}: {
  id: string
  name: string
  streamUrl: string
  source?: SourceInfo
  isVideo: boolean
  summary?: string
}) {
  const loading = source?.state === 'starting' || source?.state === 'loading'
  const ready = isVideo && (source?.state === 'running' || source?.state === 'finished')

  return (
    <Card className="overflow-hidden">
      <div className="relative aspect-video bg-slate-950">
        {ready ? (
          <>
            <img src={streamUrl} alt={name} className="h-full w-full object-contain" />
            <span className="absolute top-2 left-2 flex items-center gap-1 rounded bg-rose-600 px-2 py-0.5 text-[10px] font-semibold text-white shadow">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> LIVE CV
            </span>
          </>
        ) : loading ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-300">
            <Loader2 className="h-7 w-7 animate-spin" />
            <span className="text-xs">{source?.detail || 'Memuat model AI & membuka video…'}</span>
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center text-slate-400">
            <Video className="h-8 w-8" />
            <span className="text-xs">
              {source?.detail.startsWith('Mode simulasi')
                ? 'Berjalan dalam Mode Simulasi (tanpa video). Restart backend untuk memuat config/config.json.'
                : source?.detail || 'Menunggu koneksi backend CV…'}
            </span>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 p-3">
        <div>
          <p className="text-sm font-semibold">{name}</p>
          <p className="text-xs text-muted-foreground">
            {id} {summary ? `· ${summary}` : ''}
          </p>
        </div>
        <Badge variant={ready ? 'success' : loading ? 'warning' : 'default'}>
          {source?.state ?? 'offline'}
        </Badge>
      </div>
    </Card>
  )
}
