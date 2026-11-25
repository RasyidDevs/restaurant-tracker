import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Bell,
  Camera,
  Car,
  Clock,
  LayoutDashboard,
  LayoutGrid,
  Menu,
  Moon,
  ScanEye,
  Sparkles,
  Sun,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { alerts } from '@/data/mock'

const nav = [
  { to: '/', label: 'Ringkasan', icon: LayoutDashboard, end: true },
  { to: '/meja', label: 'Denah Meja', icon: LayoutGrid },
  { to: '/waiting-time', label: 'Waiting Time', icon: Clock },
  { to: '/alert', label: 'Alert', icon: Bell, badge: alerts.filter((a) => !a.resolved).length },
  { to: '/parkir', label: 'Parkiran', icon: Car },
  { to: '/ai-insight', label: 'AI Insight', icon: Sparkles },
  { to: '/kamera', label: 'Kamera', icon: Camera },
]

const titles: Record<string, string> = {
  '/': 'Ringkasan Hari Ini',
  '/meja': 'Denah & Status Meja',
  '/waiting-time': 'Waiting Time Pesanan',
  '/alert': 'Pusat Alert',
  '/parkir': 'Monitoring Parkiran',
  '/ai-insight': 'AI Insight & Rekomendasi',
  '/kamera': 'Kamera CCTV',
}

export function AppLayout() {
  const [dark, setDark] = useState(() => {
    try {
      return localStorage.getItem('theme') === 'dark'
    } catch {
      return false
    }
  })
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try {
      localStorage.setItem('theme', dark ? 'dark' : 'light')
    } catch {
      /* ignore */
    }
  }, [dark])

  useEffect(() => setOpen(false), [pathname])

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-sidebar transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center gap-2 border-b px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ScanEye className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <p className="font-semibold">DineSight</p>
            <p className="text-xs text-muted-foreground">Restaurant Vision AI</p>
          </div>
          <button className="ml-auto lg:hidden" onClick={() => setOpen(false)} aria-label="Tutup menu">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-accent text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
              {item.badge ? (
                <span className="ml-auto rounded-full bg-rose-500 px-1.5 text-[10px] font-semibold text-white">
                  {item.badge}
                </span>
              ) : null}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-xl border bg-muted/50 p-3 text-xs">
          <div className="flex items-center gap-2 font-medium">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            CV Engine aktif
          </div>
          <p className="mt-1 text-muted-foreground">5 dari 6 kamera online</p>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />
      )}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b bg-card/80 px-4 backdrop-blur sm:px-6">
          <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Buka menu">
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold">{titles[pathname] ?? 'DineSight'}</h1>
            <p className="hidden text-xs text-muted-foreground sm:block">
              Rabu, 25 November 2026 · Update terakhir 19:15:42
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full bg-rose-100 px-2.5 py-1 text-xs font-medium text-rose-700 sm:inline-flex dark:bg-rose-500/15 dark:text-rose-300">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rose-500" /> LIVE
            </span>
            <button
              onClick={() => setDark((d) => !d)}
              className="flex h-9 w-9 items-center justify-center rounded-lg border hover:bg-muted"
              aria-label="Ganti tema"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
              M
            </div>
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
