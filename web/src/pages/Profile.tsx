import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/context'
import { Layout, ProtectedRoute } from '../components/Layout'
import { matchesApi, type MatchResponse } from '../api/client'

export default function Profile() {
  return (
    <ProtectedRoute>
      <Layout>
        <ProfileInner />
      </Layout>
    </ProtectedRoute>
  )
}

function ProfileInner() {
  const { logout } = useAuth()
  const [tab, setTab] = useState<'info' | 'password' | 'matches'>('info')

  return (
    <div className="max-w-md space-y-6">
      <h2 className="text-2xl font-bold text-white">My Profile</h2>

      <div className="flex gap-0 border-b border-gray-800 overflow-x-auto">
        {(['info', 'matches', 'password'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px whitespace-nowrap ${
              tab === t ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {t === 'info' ? 'Account Info' : t === 'matches' ? 'Match confirmations' : 'Change Password'}
          </button>
        ))}
      </div>

      {tab === 'info' && <AccountInfo />}
      {tab === 'matches' && <PendingMatchConfirmations />}
      {tab === 'password' && <ChangePassword />}

      <div className="pt-4 border-t border-gray-800">
        <button onClick={logout}
          className="text-sm text-red-400 hover:text-red-300 transition-colors">
          Sign out of this device
        </button>
      </div>
    </div>
  )
}

function PendingMatchConfirmations() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [disputeReasons, setDisputeReasons] = useState<Record<string, string>>({})
  const [openDisputeId, setOpenDisputeId] = useState<string | null>(null)

  const pendingMatchQuery = useQuery({
    queryKey: ['pending-matches'],
    queryFn: matchesApi.pending,
    enabled: user?.role === 'PLAYER' && !!user?.player_id,
  })

  const confirmMutation = useMutation({
    mutationFn: async ({ matchId, confirmed, disputeReason }: { matchId: string; confirmed: boolean; disputeReason?: string }) =>
      matchesApi.confirm(matchId, { confirmed, dispute_reason: disputeReason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-matches'] })
      setError(null)
      setSuccess('Match response saved successfully.')
      setOpenDisputeId(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  if (user?.role !== 'PLAYER') {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-sm text-gray-300">
        Match confirmation is only available for PLAYER accounts.
      </div>
    )
  }

  if (!user?.player_id) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-sm text-gray-300">
        Link a player profile to confirm or dispute match results.
      </div>
    )
  }

  const matches = (pendingMatchQuery.data ?? []) as MatchResponse[]

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
        <div className="text-sm text-white font-semibold">Pending match confirmations</div>
        <div className="text-xs text-gray-400">Confirm or dispute matches that were submitted and are waiting for your response.</div>
      </div>

      {success && <div className="bg-green-900/40 border border-green-700 text-green-300 rounded-xl p-4 text-sm">{success}</div>}
      {error && <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-xl p-4 text-sm">{error}</div>}
      {pendingMatchQuery.isLoading && <div className="text-sm text-gray-400">Loading pending matches…</div>}
      {!pendingMatchQuery.isLoading && matches.length === 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-sm text-gray-300">
          No pending matches require your confirmation right now.
        </div>
      )}

      {matches.map(match => {
        const isOpen = openDisputeId === match.match_id
        return (
          <div key={match.match_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm text-white font-semibold">{match.player_a.name} {match.sets_won_a} - {match.sets_won_b} {match.player_b.name}</div>
                <div className="text-xs text-gray-400">Match date: {new Date(match.match_date).toLocaleDateString()}</div>
              </div>
              <div className="text-xs text-gray-400 text-right">
                Deadline: {new Date(match.confirmation_deadline).toLocaleString()}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => {
                setSuccess(null); setError(null)
                confirmMutation.mutate({ matchId: match.match_id, confirmed: true })
              }}
                className="rounded-lg bg-green-600 px-3 py-2 text-sm font-semibold text-white hover:bg-green-500 disabled:opacity-50"
                disabled={confirmMutation.isLoading}>
                Confirm
              </button>
              <button type="button" onClick={() => {
                setError(null); setSuccess(null)
                setOpenDisputeId(match.match_id)
              }}
                className="rounded-lg border border-red-600 px-3 py-2 text-sm font-semibold text-red-300 hover:border-red-500 hover:text-white">
                Dispute
              </button>
            </div>

            {isOpen && (
              <div className="space-y-3">
                <textarea
                  value={disputeReasons[match.match_id] ?? ''}
                  onChange={e => setDisputeReasons(prev => ({ ...prev, [match.match_id]: e.target.value }))}
                  rows={3}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-red-500"
                  placeholder="Explain why this result is incorrect"
                />
                <div className="flex gap-2">
                  <button type="button" onClick={() => {
                    const reason = disputeReasons[match.match_id]?.trim()
                    if (!reason) {
                      setError('Please enter a reason for dispute.')
                      return
                    }
                    confirmMutation.mutate({ matchId: match.match_id, confirmed: false, disputeReason: reason })
                  }}
                    className="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50">
                    Submit dispute
                  </button>
                  <button type="button" onClick={() => setOpenDisputeId(null)}
                    className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:border-gray-500">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function AccountInfo() {
  const { user } = useAuth()

  const formatExpiration = (expiresAt?: string | null) => {
    if (!expiresAt) return '—'
    const expiry = new Date(expiresAt)
    const now = new Date()
    const diffMs = expiry.getTime() - now.getTime()
    const minutes = Math.max(0, Math.round(diffMs / 60000))
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    const relative = diffMs <= 0 ? 'expired' : `in ${hours}h ${mins}m`
    return `${expiry.toLocaleString()} (${relative})`
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <Row label="Role" value={user?.role ?? '—'} />
      <Row label="User ID" value={<span className="font-mono text-xs text-gray-400">{user?.user_id}</span>} />
      <Row label="Academy" value={user?.academy_name
        ? <span className="font-mono text-xs text-gray-400">{user.academy_name}</span>
        : user?.academy_id
          ? <span className="font-mono text-xs text-gray-400">{user.academy_id}</span>
          : <span className="text-gray-500">Not linked to an academy</span>} />
      <Row label="Session expires" value={formatExpiration(user?.expires_at ?? null)} />
      <p className="text-xs text-gray-600 pt-2">
        To update your name, email, or phone, contact your academy administrator.
      </p>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-1">
      <div className="text-sm text-gray-400 w-36 shrink-0">{label}</div>
      <div className="text-white text-sm">{value}</div>
    </div>
  )
}

function ChangePassword() {
  const [form, setForm] = useState({ current: '', next: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [success] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault()
    if (form.next !== form.confirm) { setError('New passwords do not match'); return }
    if (form.next.length < 8) { setError('Password must be at least 8 characters'); return }
    setLoading(true); setError(null)
    try {
      // Password change endpoint not yet implemented on backend — show instructions
      throw new Error('Password change via API is not yet available. Contact your administrator.')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  if (success) return (
    <div className="bg-green-900/40 border border-green-700 text-green-300 rounded-xl p-4 text-sm">
      Password updated successfully.
    </div>
  )

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      {error && <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg p-3 text-sm">{error}</div>}
      {[
        { key: 'current', label: 'Current password' },
        { key: 'next', label: 'New password' },
        { key: 'confirm', label: 'Confirm new password' },
      ].map(({ key, label }) => (
        <div key={key}>
          <label className="block text-sm text-gray-400 mb-1">{label}</label>
          <input type="password" required value={form[key as keyof typeof form]}
            onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
      ))}
      <button type="submit" disabled={loading}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg disabled:opacity-50">
        {loading ? 'Updating…' : 'Update password'}
      </button>
    </form>
  )
}
