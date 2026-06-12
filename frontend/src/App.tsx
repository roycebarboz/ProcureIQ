import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Assess from './pages/Assess'
import Dashboard from './pages/Dashboard'
import RiskBrief from './pages/RiskBrief'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Assess />} />
        <Route path="/brief/:requestId" element={<RiskBrief />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
