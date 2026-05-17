import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { playersApi } from '../api/client'

export default function ClaimPlayer() {
  const { user, logout, updateUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const initialCode = params.get('code') ?? ''
  const claimRedirectPath = `/claim${initialCode ? `?code=${encodeURIComponent(initialCode)}` : ''}`
  const [claimCode, setClaimCode] = useState(initialCode)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (initialCode) {
      setClaimCode(initialCode)
    }
  }, [initialCode])

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="w-full max-w-lg bg-gray-900 rounded-2xl border border-gray-800 p-8 text-white shadow-xl">
          <h1 className="text-2xl font-bold mb-3">Claim player profile</h1>
          <p className="text-gray-400 mb-4">
            Create or sign in with a PLAYER account using any email. The coach-provided claim code is what links your account to the player profile.
          </p>
          {initialCode && (
            <div className="mb-4 rounded-lg border border-blue-700 bg-blue-950/30 p-4 text-sm text-blue-200">
              Your claim code is included in the email link and will be prefilled when you return to this page.
            </div>
          )}
          <div className="space-y-3">
            <button onClick={() => navigate(`/login?next=${encodeURIComponent(claimRedirectPath)}`)} className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-500">Sign in</button>
            <button onClick={() => navigate(`/login?next=${encodeURIComponent(claimRedirectPath)}`)} className="w-full rounded-lg border border-gray-700 bg-transparent px-4 py-3 text-sm font-semibold text-white hover:border-blue-500">Register as a player</button>
          </div>
        </div>
      </div>
    )
  }

  if (user.role !== 'PLAYER') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="w-full max-w-lg bg-gray-900 rounded-2xl border border-gray-800 p-8 text-white shadow-xl">
          <h1 className="text-2xl font-bold mb-3">Claim player profile</h1>
          <p className="text-gray-400 mb-6">This page is only available for PLAYER accounts. Sign out and use or create a PLAYER account to claim this profile.</p>
          <div className="space-y-3">
            <button onClick={() => { logout(); navigate(`/login?next=${encodeURIComponent(claimRedirectPath)}`) }} className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-500">Sign out and register</button>
            <button onClick={() => navigate(`/login?next=${encodeURIComponent(claimRedirectPath)}`)} className="w-full rounded-lg border border-gray-700 bg-transparent px-4 py-3 text-sm font-semibold text-white hover:border-blue-500">Sign in with a PLAYER account</button>
          </div>
        </div>
      </div>
    )
  }

  if (user.player_id) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="w-full max-w-lg bg-gray-900 rounded-2xl border border-gray-800 p-8 text-white shadow-xl">
          <h1 className="text-2xl font-bold mb-3">Player profile already claimed</h1>
          <p className="text-gray-400">Your account is already linked to a player profile. Visit your dashboard to view it.</p>
          <button onClick={() => navigate('/dashboard')} className="mt-4 inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500">Go to Dashboard</button>
        </div>
      </div>
    )
  }

  function reset() {
    setError(null)
    setSuccess(null)
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault()
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const player = await playersApi.claim(claimCode.trim())
      updateUser({
        player_id: player.player_id,
        academy_id: player.primary_academy?.academy_id ?? user?.academy_id ?? null,
        academy_name: player.primary_academy?.name ?? user?.academy_name ?? null,
      })
      setSuccess(`Successfully claimed ${player.name}. You can now access your player profile.`)
      setTimeout(() => navigate('/profile', { replace: true }), 1200)
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string }
      if (err.status === 404) {
        setError('Invalid claim code. Please verify your code and try again.')
      } else if (err.status === 422) {
        setError('This claim code has already been claimed. Ask your coach for a new one.')
      } else {
        setError(err.message ?? 'Unable to claim player record')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-gray-900 rounded-3xl border border-gray-800 p-8 shadow-xl">
          <div className="mb-6 text-center">
            <h1 className="text-3xl font-bold text-white">Claim your player profile</h1>
            <p className="text-gray-400 mt-2">Enter the registration code provided by your coach or academy.</p>
          </div>

          {error && <div className="mb-4 rounded-lg bg-red-900/40 border border-red-700 p-4 text-red-200">{error}</div>}
          {success && <div className="mb-4 rounded-lg bg-green-900/40 border border-green-700 p-4 text-green-200">{success}</div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block text-sm text-gray-400">Claim code</label>
            <input
              type="text"
              value={claimCode}
              onChange={e => { setClaimCode(e.target.value); reset() }}
              placeholder="ENTER-CODE"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
              required
            />
            <button type="submit" disabled={loading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors disabled:opacity-50">
              {loading ? 'Claiming…' : 'Claim profile'}
            </button>
          </form>

          <button type="button" onClick={() => navigate('/dashboard')} 
            className="mt-4 w-full text-sm text-gray-400 hover:text-white">Skip for now</button>
        </div>
      </div>
    </div>
  )
}
