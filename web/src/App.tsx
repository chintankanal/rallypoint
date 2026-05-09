import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import Leaderboard from './pages/Leaderboard'
import PlayerDetail from './pages/PlayerDetail'
import Dashboard from './pages/Dashboard'
import Admin from './pages/Admin'
import Profile from './pages/Profile'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/leaderboard" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/leaderboard" element={<Leaderboard />} />
      <Route path="/player/:id" element={<PlayerDetail />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/profile" element={<Profile />} />
      <Route path="*" element={<Navigate to="/leaderboard" replace />} />
    </Routes>
  )
}
