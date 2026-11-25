import { useEffect, useState } from 'react'

export type LiveConn = 'connecting' | 'live' | 'offline'

/** Berlangganan snapshot JSON dari backend lewat WebSocket (auto-reconnect tiap 3 detik). */
export function useLiveSocket<T>(path: string) {
  const [data, setData] = useState<T | null>(null)
  const [conn, setConn] = useState<LiveConn>('connecting')

  useEffect(() => {
    let closed = false
    let ws: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}${path}`)
      ws.onopen = () => setConn('live')
      ws.onmessage = (e) => {
        try {
          setData(JSON.parse(e.data))
        } catch {
          /* abaikan pesan rusak */
        }
      }
      ws.onclose = () => {
        if (closed) return
        setConn('offline')
        retry = setTimeout(connect, 3000)
      }
      ws.onerror = () => ws?.close()
    }
    connect()

    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [path])

  return { data, conn }
}
