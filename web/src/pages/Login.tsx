import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { authApi } from '../api/client'

type Screen = 'login' | 'register'
type LoginMethod = 'password' | 'otp'
type OtpStep = 'enter-email' | 'enter-code'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const next = params.get('next') ?? '/'
  const [screen, setScreen] = useState<Screen>('login')

  async function doLogin(body: { email: string; password?: string; otp_code?: string }) {
    const resp = await authApi.login(body)
    login(resp)
    const destination = next || '/'
    if (resp.role === 'PLAYER' && !resp.player_id) {
      if (next && next !== '/') {
        navigate(destination, { replace: true })
      } else {
        navigate('/onboarding', { replace: true })
      }
      return
    }
    navigate(destination, { replace: true })
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-bold text-white mb-1 text-center">JLRS</h1>
        <p className="text-gray-400 text-sm text-center mb-4">Junior League Rating System</p>
        {next !== '/' && (
          <div className="mb-4 rounded-lg border border-blue-700 bg-blue-950/30 p-3 text-sm text-blue-200 text-center">
            After signing in or registering, you will be returned to the claim page and the code you received in email will be prefilled.
          </div>
        )}

        <div className="flex rounded-xl overflow-hidden border border-gray-700 mb-6">
          <TabBtn active={screen === 'login'} onClick={() => setScreen('login')}>Sign In</TabBtn>
          <TabBtn active={screen === 'register'} onClick={() => setScreen('register')}>Register</TabBtn>
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 shadow-xl">
          {screen === 'login'
            ? <LoginForm doLogin={doLogin} />
            : <RegisterForm onSuccess={() => setScreen('login')} />
          }
        </div>
      </div>
    </div>
  )
}

// ── Login form ────────────────────────────────────────────────────────────────

function LoginForm({ doLogin }: { doLogin: (body: { email: string; password?: string; otp_code?: string }) => Promise<void> }) {
  const [method, setMethod] = useState<LoginMethod>('password')
  const [otpStep, setOtpStep] = useState<OtpStep>('enter-email')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handlePasswordLogin(ev: React.FormEvent) {
    ev.preventDefault()
    setLoading(true); setError(null)
    try { await doLogin({ email, password }) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Invalid email or password') }
    finally { setLoading(false) }
  }

  async function handleSendOtp(ev: React.FormEvent) {
    ev.preventDefault()
    setLoading(true); setError(null)
    try { await authApi.requestOtp(email); setOtpStep('enter-code') }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed to send code') }
    finally { setLoading(false) }
  }

  async function handleOtpLogin(ev: React.FormEvent) {
    ev.preventDefault()
    setLoading(true); setError(null)
    try { await doLogin({ email, otp_code: otpCode }) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Invalid or expired code') }
    finally { setLoading(false) }
  }

  function switchMethod(m: LoginMethod) {
    setMethod(m); setError(null); setOtpStep('enter-email'); setOtpCode('')
  }

  return (
    <>
      <div className="flex rounded-lg overflow-hidden border border-gray-700 mb-5">
        <TabBtn active={method === 'password'} onClick={() => switchMethod('password')}>Password</TabBtn>
        <TabBtn active={method === 'otp'} onClick={() => switchMethod('otp')}>Email code</TabBtn>
      </div>

      {error && <ErrorBanner>{error}</ErrorBanner>}

      {method === 'password' && (
        <form onSubmit={handlePasswordLogin} className="space-y-4">
          <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" />
          <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" />
          <SubmitBtn loading={loading}>Sign in</SubmitBtn>
        </form>
      )}

      {method === 'otp' && otpStep === 'enter-email' && (
        <form onSubmit={handleSendOtp} className="space-y-4">
          <p className="text-gray-400 text-sm">We'll email you a 6-digit login code — no password needed.</p>
          <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" />
          <SubmitBtn loading={loading}>Send login code →</SubmitBtn>
        </form>
      )}

      {method === 'otp' && otpStep === 'enter-code' && (
        <form onSubmit={handleOtpLogin} className="space-y-4">
          <div className="bg-blue-900/30 border border-blue-800 rounded-lg p-3 text-sm text-blue-300">
            Code sent to <strong>{email}</strong>. Check your inbox.
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">6-digit code</label>
            <input
              type="text" inputMode="numeric" maxLength={6} autoFocus
              value={otpCode} onChange={e => setOtpCode(e.target.value.replace(/\D/g, ''))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-3 text-white text-2xl tracking-[0.6em] text-center font-mono focus:outline-none focus:border-blue-500"
              placeholder="——————"
            />
          </div>
          <SubmitBtn loading={loading}>Sign in</SubmitBtn>
          <button type="button" onClick={() => { setOtpStep('enter-email'); setOtpCode(''); setError(null) }}
            className="w-full text-xs text-gray-500 hover:text-gray-300">← Use a different email</button>
        </form>
      )}
    </>
  )
}

// ── Register form ─────────────────────────────────────────────────────────────

function RegisterForm({ onSuccess }: { onSuccess: () => void }) {
  const [form, setForm] = useState({
    name: '', email: '', password: '', phone: '', gender: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  function set(key: keyof typeof form) {
    return (v: string) => setForm(f => ({ ...f, [key]: v }))
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault()
    setLoading(true); setError(null)
    try {
      await authApi.register({
        name: form.name, email: form.email, password: form.password,
        role: 'PLAYER',
        phone: form.phone || undefined,
        gender: form.gender || undefined,
      })
      setDone(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  if (done) return (
    <div className="text-center space-y-4 py-2">
      <div className="text-4xl mb-2">✓</div>
      <div className="text-green-400 text-lg font-semibold">Account created!</div>
      <p className="text-gray-400 text-sm">You can now sign in with your email and password.</p>
      <button onClick={onSuccess}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors">
        Go to Sign In
      </button>
    </div>
  )

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <ErrorBanner>{error}</ErrorBanner>}

      <Field label="Full name" type="text" value={form.name} onChange={set('name')} placeholder="Arjun Sharma" />
      <Field label="Email address" type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" />
      <Field label="Password" type="password" value={form.password} onChange={set('password')} placeholder="Min 8 characters" />

      <div className="rounded-lg border border-dashed border-gray-700 p-4 bg-gray-950/80">
        <p className="text-sm text-gray-400">New accounts are created as PLAYER only. You may use any email address; the claim code is what links your account to the player profile.</p>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Gender <span className="text-gray-600">(optional)</span></label>
        <select value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))}
          className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-blue-500">
          <option value="">Prefer not to say</option>
          <option value="MALE">Male</option>
          <option value="FEMALE">Female</option>
        </select>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Phone <span className="text-gray-600">(optional)</span></label>
        <input type="tel" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
          placeholder="+91 98765 43210"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 placeholder-gray-600" />
      </div>

      <SubmitBtn loading={loading}>Create account</SubmitBtn>
    </form>
  )
}

// ── Shared primitives ─────────────────────────────────────────────────────────

function Field({ label, type, value, onChange, placeholder }: {
  label: string; type: string; value: string
  onChange: (v: string) => void; placeholder?: string
}) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-1">{label}</label>
      <input type={type} required value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 placeholder-gray-600" />
    </div>
  )
}

function SubmitBtn({ loading, children }: { loading: boolean; children: React.ReactNode }) {
  return (
    <button type="submit" disabled={loading}
      className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors disabled:opacity-50">
      {loading ? 'Please wait…' : children}
    </button>
  )
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick}
      className={`flex-1 py-2.5 text-sm font-medium transition-colors ${active ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}>
      {children}
    </button>
  )
}

function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg p-3 mb-4 text-sm">{children}</div>
  )
}
