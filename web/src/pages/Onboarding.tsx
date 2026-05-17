import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'

export default function Onboarding() {
  const { user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!user) {
      navigate('/login', { replace: true })
    }
  }, [user, navigate])

  if (!user) {
    return null
  }

  if (user.role !== 'PLAYER') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="w-full max-w-lg rounded-3xl border border-gray-800 bg-gray-900 p-8 text-white shadow-xl">
          <h1 className="text-3xl font-bold mb-4">Onboarding not available</h1>
          <p className="text-gray-400">This onboarding flow is only available for PLAYER accounts. Use your dashboard to continue.</p>
          <button onClick={() => navigate('/dashboard')} className="mt-6 inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-500">Go to Dashboard</button>
        </div>
      </div>
    )
  }

  if (user.player_id) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="w-full max-w-lg rounded-3xl border border-gray-800 bg-gray-900 p-8 text-white shadow-xl">
          <h1 className="text-3xl font-bold mb-4">You’re all set</h1>
          <p className="text-gray-400">Your account is already linked to a player profile. Continue to your dashboard to view your details.</p>
          <button onClick={() => navigate('/dashboard')} className="mt-6 inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-500">Go to Dashboard</button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-2xl rounded-3xl border border-gray-800 bg-gray-900 p-8 shadow-xl">
        <div className="mb-6 text-center">
          <h1 className="text-4xl font-bold text-white">Welcome to JLRS</h1>
          <p className="mt-3 text-gray-400">You’ve created a player account. Now choose how you want to continue.</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-3xl border border-gray-800 bg-gray-950/60 p-6">
            <div className="text-sm uppercase tracking-[0.2em] text-blue-400 mb-3">New to JLRS</div>
            <h2 className="text-2xl font-semibold text-white mb-3">I’m a new player</h2>
            <p className="text-gray-400 mb-6">If your coach hasn’t provided a claim code yet, ask them to provision your player profile. Once they do, return here to claim it.</p>
            <button onClick={() => navigate('/dashboard')} className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-500">Go to dashboard</button>
          </div>

          <div className="rounded-3xl border border-gray-800 bg-gray-950/60 p-6">
            <div className="text-sm uppercase tracking-[0.2em] text-green-400 mb-3">Already registered</div>
            <h2 className="text-2xl font-semibold text-white mb-3">I have a claim code</h2>
            <p className="text-gray-400 mb-6">Use a code from your coach or academy to link your account with your official player profile.</p>
            <button onClick={() => navigate('/claim')} className="w-full rounded-lg bg-green-600 px-4 py-3 text-sm font-semibold text-white hover:bg-green-500">Claim player profile</button>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-dashed border-gray-700 bg-gray-950/50 p-4 text-sm text-gray-400">
          <p><strong>Tip:</strong> If you don’t have a claim code yet, your coach can create your player profile on the dashboard and share the code with you.</p>
        </div>
      </div>
    </div>
  )
}
