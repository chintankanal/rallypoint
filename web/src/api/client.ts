const BASE = '/api/v1'

function getToken(): string | null {
  return localStorage.getItem('jlrs_token')
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
    throw Object.assign(new Error(msg ?? 'Request failed'), { status: res.status, data: err })
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  token: string
  user_id: string
  role: 'ADMIN' | 'COACH' | 'PLAYER' | 'REFEREE' | 'UMPIRE'
  academy_id: string | null
  academy_name: string | null
  player_id: string | null
  expires_at: string
}

export const authApi = {
  login: (body: { email: string; password?: string; otp_code?: string }) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  requestOtp: (email: string) =>
    request<{ detail: string }>('/auth/request-otp', { method: 'POST', body: JSON.stringify({ email }) }),
  register: (body: {
    name: string; email: string; password: string; role: string
    gender?: string; academy_id?: string; phone?: string
  }) =>
    request<{ user_id: string; name: string; email: string; role: string }>(
      '/auth/register', { method: 'POST', body: JSON.stringify(body) }
    ),
}

// ── Academies ─────────────────────────────────────────────────────────────────

export interface AcademyListItem {
  academy_id: string
  name: string
  city: string
  state: string
  status: string
}

export interface AcademyDetail extends AcademyListItem {
  location: string
  min_tables: number
  current_asi: number | null
  asi_player_count: number | null
  active_player_count: number
  created_at: string
}

export interface TierDistribution {
  BEGINNER: number
  INTERMEDIATE: number
  ADVANCED: number
  ELITE: number
  NATIONAL_TRACK: number
}

export interface AcademyStats {
  academy_id: string
  tables_available: number
  active_player_count: number
  coach_count: number
  total_match_volume: number
  matches_30_days: number
  current_asi: number | null
  tier_distribution: TierDistribution
}

export const academiesApi = {
  list: (status?: string) => {
    const q = status ? `?status=${status}` : ''
    return request<{ items: AcademyListItem[] }>(`/academies${q}`)
  },
  get: (id: string) => request<AcademyDetail>(`/academies/${id}`),
  create: (body: { name: string; location: string; city: string; state: string; min_tables: number }) =>
    request<AcademyDetail>('/academies', { method: 'POST', body: JSON.stringify(body) }),
  asiHistory: (id: string, limit = 12) =>
    request<{ academy_id: string; items: ASIPoint[] }>(`/academies/${id}/asi-history?limit=${limit}`),
  leaderboard: (id: string, params?: { tier?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.tier) q.set('tier', params.tier)
    if (params?.limit !== undefined) q.set('limit', String(params.limit))
    if (params?.offset !== undefined) q.set('offset', String(params.offset))
    return request<LeaderboardResponse>(`/academies/${id}/leaderboard?${q}`)
  },
  getStats: (id: string) =>
    request<AcademyStats>(`/academies/${id}/stats`),
}

export interface ASIPoint {
  history_id: string
  asi_value: number | null
  qualifying_player_count: number
  calculation_basis: string
  global_average_at_calculation: number
  calculated_at: string
}

// ── Leaderboard ───────────────────────────────────────────────────────────────

export interface LeaderboardEntry {
  rank: number
  player_id: string
  name: string
  current_rating: number
  tier: string
  academy_name: string | null
  is_provisional: boolean
  rated_matches: number
  last_match_date: string | null
  gender: string | null
  age_group: string | null
  claim_code?: string | null
  is_claimed?: boolean | null
}

export interface LeaderboardResponse {
  total: number
  limit: number
  offset: number
  items: LeaderboardEntry[]
}

export interface OverviewStats {
  total_players: number
  matches_processed: number
  participating_academies: number
}

export interface AgeGroupEntry {
  rank: number
  player_id: string
  name: string
  current_rating: number
  tier: string
  academy_name: string | null
  age_jan1: number
  percentile: number
  gender: string | null
  age_group: string | null
}

export const leaderboardApi = {
  global: (params?: { tier?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.tier) q.set('tier', params.tier)
    if (params?.limit !== undefined) q.set('limit', String(params.limit))
    if (params?.offset !== undefined) q.set('offset', String(params.offset))
    return request<LeaderboardResponse>(`/leaderboard?${q}`)
  },
  ageGroup: (ageGroup: string) =>
    request<{ age_group: string; total: number; items: AgeGroupEntry[] }>(`/analytics/leaderboard?age_group=${ageGroup}`),
}

export const overviewApi = {
  get: () => request<OverviewStats>('/overview'),
}

// ── Players ───────────────────────────────────────────────────────────────────

export interface PlayerSearchResult {
  player_id: string
  name: string
  current_rating: number
  academy_name: string | null
}

export interface PlayerDirectoryItem {
  player_id: string
  name: string
  current_rating: number
  status: string
  academy_id: string
  academy_name: string
}

export interface PlayerDetail {
  player_id: string
  name: string
  date_of_birth: string
  gender: 'MALE' | 'FEMALE' | null
  nationality: string | null
  current_rating: number
  rated_matches_completed: number
  virtual_matches: number
  seeding_level: string
  primary_academy: { academy_id: string; name: string; city: string; state: string }
  last_match_date: string | null
  guardian_name: string | null
  guardian_phone: string | null
  contact_email: string | null
  status: string
  is_claimed: boolean
  claim_code: string | null
  created_at: string
}

export interface ComputedStats {
  player_id: string
  tier: string
  confidence_ratio: number
  is_provisional: boolean
  provisional_matches_remaining: number
  weeks_inactive: number | null
  age_as_of_jan1: number
  age_group: string
  total_matches: number
  inactivity_decay_active: boolean
}

export interface RatingHistoryEntry {
  history_id: string
  match_id: string
  rating_before: number
  rating_after: number
  delta: number
  k_base: number | null
  k_eff: number | null
  k_shared: number | null
  expected_score: number | null
  actual_score: number | null
  age_bonus: number | null
  tier_before: string | null
  tier_after: string | null
  is_rollback: boolean
  match_date: string | null
  created_at: string
  opponent_name: string | null
  result: 'WIN' | 'LOSS'
  delta_breakdown: Record<string, unknown> | null
  event_id: string | null
  event_name: string | null
  event_type: string | null
  session_id: string | null
  session_date: string | null
  match_category: string | null
  sets_won_a: number | null
  sets_won_b: number | null
  confirmation_status: string | null
  diminishing_signal_applied: boolean | null
  opponent_rating_before: number | null
}

export const playersApi = {
  listAll: () => request<{ items: PlayerDirectoryItem[] }>('/players'),
  search: (q: string, academyId?: string) => {
    const params = new URLSearchParams({ q })
    if (academyId) params.set('academy_id', academyId)
    return request<{ items: PlayerSearchResult[] }>(`/players/search?${params}`)
  },
  get: (id: string) => request<PlayerDetail>(`/players/${id}`),
  computedStats: (id: string) => request<ComputedStats>(`/players/${id}/computed-stats`),
  ratingHistory: (id: string, params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.limit !== undefined) q.set('limit', String(params.limit))
    if (params?.offset !== undefined) q.set('offset', String(params.offset))
    return request<{ total: number; items: RatingHistoryEntry[] }>(`/players/${id}/rating-history?${q}`)
  },
  velocity: (id: string, period: '1m' | '3m' | '6m' | '1y') =>
    request<VelocityReport>(`/analytics/players/${id}/velocity?period=${period}`),
  create: (body: {
    name: string; date_of_birth: string; gender: string; primary_academy_id: string
    seeding_level: string; seeding_reference?: string; nationality?: string
    guardian_name?: string; guardian_phone?: string; contact_email?: string
    virtual_matches?: number
  }) => request<PlayerDetail>('/players', { method: 'POST', body: JSON.stringify(body) }),
  linkAccount: (playerId: string, userId: string) =>
    request<PlayerDetail>(`/players/${playerId}/link-account`, { method: 'PATCH', body: JSON.stringify({ user_id: userId }) }),
  claim: (claimCode: string) =>
    request<PlayerDetail>('/players/claim', { method: 'POST', body: JSON.stringify({ claim_code: claimCode }) }),
  fixtures: (playerId: string) =>
    request<PlayerEventFixtures>(`/players/${playerId}/fixtures`),
  sendClaim: (playerId: string) =>
    request<{ detail: string }>(`/players/${playerId}/send-claim-code`, { method: 'POST' }),
}

export interface VelocityReport {
  player_id: string
  period: string
  start_rating: number | null
  end_rating: number | null
  rating_change: number
  matches_played: number
  wins: number
  win_rate: number
  stretch_matches: number
  stretch_wins: number
  stretch_win_rate: number | null
  tier_changes: number
}

// ── Seasons ───────────────────────────────────────────────────────────────────

export interface Season {
  season_id: string
  name: string
  start_date: string
  end_date: string
  status: string
  created_at: string
}

export const seasonsApi = {
  list: () => request<Season[]>('/seasons'),
  create: (body: { name: string; start_date: string; end_date: string }) =>
    request<Season>('/seasons', { method: 'POST', body: JSON.stringify(body) }),
  updateStatus: (id: string, status: string) =>
    request<Season>(`/seasons/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
}

// ── Events ────────────────────────────────────────────────────────────────────

export interface Event {
  event_id: string
  name: string
  scheduling_mode: string
  event_type: string
  default_match_format: string | null
  tournament_format: string | null
  status: string
  fixture_state: string | null
  start_date: string
  end_date: string | null
  season: { season_id: string; name: string } | null
  participating_academies: { academy_id: string; name: string }[]
  created_at: string
}

export interface EventListItem {
  event_id: string
  name: string
  scheduling_mode: string
  event_type: string
  status: string
  start_date: string
  end_date: string | null
  host_academy_id?: string
  participating_academies?: { academy_id: string; name: string }[]
}

export const eventsApi = {
  list: () => request<{ items: EventListItem[] }>('/events'),
  get: (id: string) => request<Event>(`/events/${id}`),
  create: (body: {
    name: string; scheduling_mode: string; event_type: string
    start_date: string; end_date?: string; season_id?: string
    default_match_format?: string; tournament_format?: string
    host_academy_id?: string; participating_academy_ids?: string[]
  }) => request<Event>('/events', { method: 'POST', body: JSON.stringify(body) }),
  updateStatus: (id: string, status: string) =>
    request<Event>(`/events/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  addAcademy: (id: string, academy_id: string) =>
    request<Event>(`/events/${id}/academies`, { method: 'POST', body: JSON.stringify({ academy_id }) }),
  listPlayers: (id: string) => request<EventRoster>(`/events/${id}/players`),
  registerPlayer: (id: string, player_id: string) =>
    request<EventRoster>(`/events/${id}/players`, { method: 'POST', body: JSON.stringify({ player_id }) }),
  removePlayer: (id: string, player_id: string) =>
    request<void>(`/events/${id}/players/${player_id}`, { method: 'DELETE' }),
  generateFixtures: (id: string, num_tables: number, fixture_strategy: string = 'TIER_MATCHED') =>
    request<EventFixtures>(`/events/${id}/generate-fixtures`, { method: 'POST', body: JSON.stringify({ num_tables, fixture_strategy }) }),
  getFixtures: (id: string) => request<EventFixtures>(`/events/${id}/fixture-slots`),
  getFixtureStatus: (id: string) => request<FixtureStatus>(`/events/${id}/fixtures/status`),
  lockFixtures: (id: string) => request<{ fixture_state: string }>(`/events/${id}/fixtures/lock`, { method: 'POST' }),
  applyRatings: (id: string) => request<{ fixture_state: string; matches_processed: number }>(`/events/${id}/apply-ratings`, { method: 'POST' }),
}

// ── Event player roster ───────────────────────────────────────────────────────

export interface EventPlayer {
  registration_id: string
  player_id: string
  name: string
  academy_id: string
  academy_name: string
  current_rating: number
  status: string
  registered_at: string
}

export interface EventRoster {
  event_id: string
  total: number
  items: EventPlayer[]
}

// ── Event fixture types ───────────────────────────────────────────────────────

export interface EventFixturePlayer {
  player_id: string
  name: string
  current_rating: number
  academy_id: string
  academy_name: string
}

export interface EventFixtureSlot {
  slot_id: string
  round_number: number
  table_number: number
  match_category: string
  fixture_strategy: string
  player_a: EventFixturePlayer
  player_b: EventFixturePlayer | null
  expected_rating_gap: number
  status: string
  match_id: string | null
}

export interface EventFixtures {
  event_id: string
  total_rounds: number
  total_slots: number
  cross_academy_pct: number
  fixture_state: string | null
  slots: EventFixtureSlot[]
}

export interface PlayerEventFixtureItem {
  event_id: string
  name: string
  scheduling_mode: string
  event_type: string
  status: string
  fixture_state: string | null
  start_date: string
  end_date: string | null
  default_match_format: string | null
  slots: EventFixtureSlot[]
}

export interface PlayerEventFixtures {
  player_id: string
  items: PlayerEventFixtureItem[]
}

export interface FixtureStatus {
  fixture_state: string | null
  can_regenerate: boolean
  reason: string | null
}

// ── Matches ───────────────────────────────────────────────────────────────────

export interface SetScore {
  set_number: number
  points_a: number
  points_b: number
}

export interface MatchResponse {
  match_id: string
  event_id: string
  player_a: { player_id: string; name: string; current_rating: number }
  player_b: { player_id: string; name: string; current_rating: number }
  sets_won_a: number
  sets_won_b: number
  match_format: string
  is_retirement: boolean
  winner_id: string
  rating_eligible: boolean
  not_eligible_reason: string | null
  confirmation_status: string
  confirmation_deadline: string
  match_date: string
  set_scores?: SetScore[] | null
}

export const matchesApi = {
  submit: (body: {
    event_id: string; player_a_id: string; player_b_id: string
    match_format: string; sets_won_a: number; sets_won_b: number
    match_date: string; is_retirement?: boolean; session_id?: string
    fixture_slot_id?: string; set_scores?: Array<{ points_a: number; points_b: number }> | null
  }) => request<MatchResponse>('/matches', { method: 'POST', body: JSON.stringify(body) }),
  get: (id: string) => request<MatchResponse>(`/matches/${id}`),
  confirm: (id: string, body: { confirmed: boolean; dispute_reason?: string }) =>
    request<MatchResponse>(`/matches/${id}/confirm`, { method: 'POST', body: JSON.stringify(body) }),  pending: () => request<MatchResponse[]>('/matches/pending'),}

// ── Sessions & Fixtures ───────────────────────────────────────────────────────

export interface SessionSummary {
  session_id: string
  event_id: string
  session_date: string
  session_minutes: number
  num_tables: number
  match_format: string
  bootstrap_phase: string
  matches_per_player: number
  present_player_count: number
  status: string
  generated_at: string | null
  created_at: string
}

export interface FixturePlayer {
  player_id: string
  name: string
  current_rating: number
}

export interface FixtureSlot {
  slot_id: string
  round_number: number
  sub_round: string | null
  table_number: number
  match_category: string
  player_a: FixturePlayer
  player_b: FixturePlayer | null
  expected_rating_gap: number
  status: string
  match_id: string | null
  match_result: {
    sets_won_a: number
    sets_won_b: number
    winner_id: string
    confirmation_status: string
    is_retirement: boolean
  } | null
}

export interface FixturesResponse {
  session_id: string
  bootstrap_phase: string
  matches_per_player: number
  fixture_slots_created: number
  slots: FixtureSlot[]
}

export const sessionsApi = {
  list: (eventId: string) =>
    request<SessionSummary[]>(`/events/${eventId}/sessions`),
  create: (eventId: string, body: { session_date: string; num_tables: number; session_minutes: number; match_format?: string }) =>
    request<SessionSummary>(`/events/${eventId}/sessions`, { method: 'POST', body: JSON.stringify(body) }),
  generateFixtures: (sessionId: string, playerIds: string[]) =>
    request<{ bootstrap_phase: string; matches_per_player: number; fixture_slots_created: number }>(
      `/sessions/${sessionId}/generate-fixtures`,
      { method: 'POST', body: JSON.stringify({ player_ids: playerIds }) },
    ),
  fixtures: (sessionId: string) =>
    request<FixturesResponse>(`/sessions/${sessionId}/fixtures`),
  updateStatus: (sessionId: string, status: string) =>
    request<SessionSummary>(`/sessions/${sessionId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  applyRatings: (sessionId: string) =>
    request<{
      session_id: string
      matches_rated: number
      matches_auto_confirmed: number
      tier_changes: { player_id: string; tier_before: string; tier_after: string }[]
      already_up_to_date: boolean
    }>(`/sessions/${sessionId}/apply-ratings`, { method: 'POST' }),
}

// ── Disputes ──────────────────────────────────────────────────────────────────

export interface Dispute {
  dispute_id: string
  match_id: string
  dispute_reason: string
  status: string
  resolution_deadline: string
  created_at: string
}

export const disputesApi = {
  list: (params?: { status?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.limit !== undefined) q.set('limit', String(params.limit))
    return request<{ total: number; items: Dispute[] }>(`/disputes?${q}`)
  },
  get: (id: string) => request<Dispute>(`/disputes/${id}`),
  updateStatus: (id: string, status: string) =>
    request<Dispute>(`/disputes/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  resolve: (id: string, body: { resolution: string }) =>
    request<Dispute>(`/disputes/${id}/resolve`, { method: 'POST', body: JSON.stringify(body) }),
}

// ── Config ────────────────────────────────────────────────────────────────────

export interface ConfigEntry { key: string; value: string; description: string | null }

export const configApi = {
  get: () => request<{ items: ConfigEntry[] }>('/config'),
  update: (key: string, value: string, reason: string) =>
    request<ConfigEntry>('/config', { method: 'PATCH', body: JSON.stringify({ key, value, reason }) }),
}
