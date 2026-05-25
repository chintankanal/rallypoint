import { useState, type ReactNode } from 'react'
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

  return (
    <div className="max-w-4xl space-y-6">
      <div className="rounded-2xl border border-gray-800 bg-gray-900 p-5 text-sm text-gray-300">
        Use the top navigation Dashboard link to view your match confirmations and event fixtures.
      </div>

      <div className="space-y-6">
        <AccountInfo />
        <ChangePassword />
      </div>

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

  const formatExpiration = (expiresAt?: string | null) => {
    if (!expiresAt) return '�'
    const date = new Date(expiresAt)
    return date.toLocaleString()
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <div className="text-sm text-gray-400">Account details</div>
      <Row label="Role" value={user?.role ?? '�'} />
      <Row label="User ID" value={<span className="font-mono text-xs text-gray-400">{user?.user_id}</span>} />
      <Row label="Academy" value={
        user?.academy_name
          ? <span className="font-mono text-xs text-gray-400">{user.academy_name}</span>
          : user?.academy_id
            ? <span className="font-mono text-xs text-gray-400">{user.academy_id}</span>
            : <span className="text-gray-500">Not linked to an academy</span>
      } />
      <Row label="Session expires" value={formatExpiration(user?.expires_at ?? null)} />
      <p className="text-xs text-gray-600 pt-2">
        To update your name, email, or phone, contact your academy administrator.
      </p>
    </div>
  )
}

function Row({ label, value }: { label: string; value: ReactNode }) {
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
  const [loading, setLoading] = useState(false)

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault()
    if (form.next !== form.confirm) {
      setError('New passwords do not match')
      return
    }
    if (form.next.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    setError(null)
    try {
      throw new Error('Password change via API is not yet available. Contact your administrator.')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

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
          <input
            type="password"
            required
            value={form[key as keyof typeof form]}
            onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
      ))}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg disabled:opacity-50"
      >
        {loading ? 'Updating�' : 'Update password'}
      </button>
    </form>
  )
}
