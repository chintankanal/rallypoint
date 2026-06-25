import { Link, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/context'

const TIER_COLORS: Record<string, string> = {
  BEGINNER: 'bg-gray-500',
  INTERMEDIATE: 'bg-blue-500',
  ADVANCED: 'bg-green-500',
  ELITE: 'bg-purple-500',
  NATIONAL_TRACK: 'bg-yellow-500',
}

export function TierBadge({ tier }: { tier: string }) {
  const color = TIER_COLORS[tier] ?? 'bg-gray-400'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-white text-xs font-semibold ${color}`}>
      {tier.replace('_', ' ')}
    </span>
  )
}

export function CRBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  )
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  function handleLogout() {
    logout()
    navigate('/')
  }

  const navLink = (to: string, label: string) => (
    <Link
      to={to}
      className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
        location.pathname.startsWith(to)
          ? 'bg-blue-700 text-white'
          : 'text-gray-300 hover:text-white hover:bg-gray-700'
      }`}
    >
      {label}
    </Link>
  )

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <nav className="bg-gray-900 border-b border-gray-800 px-4 py-3 flex items-center gap-4 flex-wrap">
        <Link to="/" className="font-bold text-blue-400 text-lg tracking-tight mr-2">
          JLRS
        </Link>
        {navLink('/leaderboard', 'Leaderboard')}
        {user?.player_id && navLink('/player/dashboard', 'Dashboard')}
        {user?.player_id && navLink(`/player/${user.player_id}`, 'My Performance')}
        {user?.role === 'COACH' && navLink('/dashboard', 'Dashboard')}
        {user?.role === 'ADMIN' && navLink('/admin', 'Admin')}
        {user && navLink('/profile', 'My Profile')}
        <div className="ml-auto flex items-center gap-3">
          {user ? (
            <>
              <span className="text-xs text-gray-400 hidden sm:block">
                {user.name ?? user.role}
                {user.academy_name && ` · ${user.academy_name}`}
              </span>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-400 hover:text-white transition-colors"
              >
                Logout
              </button>
            </>
          ) : (
            <Link to="/login" className="text-sm text-blue-400 hover:text-blue-300">
              Login
            </Link>
          )}
        </div>
      </nav>
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">{children}</main>
      <footer className="text-center text-gray-600 text-xs py-4 border-t border-gray-800">
        JLRS © {new Date().getFullYear()}
      </footer>
    </div>
  )
}

export function ProtectedRoute({
  roles,
  children,
}: {
  roles?: Array<'ADMIN' | 'COACH' | 'PLAYER' | 'REFEREE' | 'UMPIRE'>
  children: React.ReactNode
}) {
  const { user, recentlyLoggedOut } = useAuth()

  if (!user) {
    // If we've just logged out, allow the logout navigation to / to proceed
    if (recentlyLoggedOut) return null
    return <Navigate to="/login" replace />
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 text-lg">Access denied — insufficient role.</p>
      </div>
    )
  }
  return <>{children}</>
}

export function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

export function ErrorMsg({ message }: { message: string }) {
  return (
    <div className="bg-red-900/40 border border-red-700 text-red-300 rounded p-4 my-4 text-sm">
      {message}
    </div>
  )
}
