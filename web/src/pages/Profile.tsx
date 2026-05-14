import { useState } from 'react'
import { useAuth } from '../auth/context'
import { Layout, ProtectedRoute } from '../components/Layout'

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
  const [tab, setTab] = useState<'info' | 'password'>('info')

  return (
    <div className="max-w-md space-y-6">
      <h2 className="text-2xl font-bold text-white">My Profile</h2>

      <div className="flex gap-0 border-b border-gray-800">
        {(['info', 'password'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {t === 'info' ? 'Account Info' : 'Change Password'}
          </button>
        ))}
      </div>

      {tab === 'info' && <AccountInfo />}
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

function AccountInfo() {
  const { user } = useAuth()

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <Row label="Role" value={user?.role ?? '—'} />
      <Row label="User ID" value={<span className="font-mono text-xs text-gray-400">{user?.user_id}</span>} />
      <Row label="Academy ID" value={user?.academy_id
        ? <span className="font-mono text-xs text-gray-400">{user.academy_id}</span>
        : <span className="text-gray-500">Not linked to an academy</span>} />
      <Row label="Session expires" value={user?.expires_at ? new Date(user.expires_at).toLocaleString() : '—'} />
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
