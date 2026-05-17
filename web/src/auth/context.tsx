import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import type { TokenResponse } from '../api/client'

interface AuthUser {
  user_id: string
  role: 'ADMIN' | 'COACH' | 'PLAYER' | 'REFEREE' | 'UMPIRE'
  academy_id: string | null
  academy_name: string | null
  player_id: string | null
  expires_at: string
}

interface AuthContextValue {
  user: AuthUser | null
  token: string | null
  login: (resp: TokenResponse) => void
  logout: () => void
  updateUser: (updates: Partial<AuthUser>) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function parseStored(): { user: AuthUser; token: string } | null {
  const token = localStorage.getItem('jlrs_token')
  const raw = localStorage.getItem('jlrs_user')
  if (!token || !raw) return null
  try {
    const user = JSON.parse(raw) as AuthUser
    if (new Date(user.expires_at) < new Date()) {
      localStorage.removeItem('jlrs_token')
      localStorage.removeItem('jlrs_user')
      return null
    }
    return { user, token }
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const stored = parseStored()
  const [user, setUser] = useState<AuthUser | null>(stored?.user ?? null)
  const [token, setToken] = useState<string | null>(stored?.token ?? null)

  const login = useCallback((resp: TokenResponse) => {
    const u: AuthUser = {
      user_id: resp.user_id,
      role: resp.role,
      academy_id: resp.academy_id,
      academy_name: resp.academy_name ?? null,
      player_id: resp.player_id ?? null,
      expires_at: resp.expires_at,
    }
    localStorage.setItem('jlrs_token', resp.token)
    localStorage.setItem('jlrs_user', JSON.stringify(u))
    setToken(resp.token)
    setUser(u)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('jlrs_token')
    localStorage.removeItem('jlrs_user')
    setToken(null)
    setUser(null)
  }, [])

  const updateUser = useCallback((updates: Partial<AuthUser>) => {
    setUser((current) => {
      if (!current) return current
      const next = { ...current, ...updates }
      localStorage.setItem('jlrs_user', JSON.stringify(next))
      return next
    })
  }, [])

  return <AuthContext.Provider value={{ user, token, login, logout, updateUser }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
