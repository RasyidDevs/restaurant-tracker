import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import Dashboard from '@/pages/Dashboard'
import TableMap from '@/pages/TableMap'
import WaitingTime from '@/pages/WaitingTime'
import Alerts from '@/pages/Alerts'
import Parking from '@/pages/Parking'
import AiInsights from '@/pages/AiInsights'
import Cameras from '@/pages/Cameras'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="meja" element={<TableMap />} />
          <Route path="waiting-time" element={<WaitingTime />} />
          <Route path="alert" element={<Alerts />} />
          <Route path="parkir" element={<Parking />} />
          <Route path="ai-insight" element={<AiInsights />} />
          <Route path="kamera" element={<Cameras />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
