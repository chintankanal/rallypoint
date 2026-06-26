import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/context'
import { Layout, ProtectedRoute } from '../components/Layout'
import {
  matchesApi,
  playersApi,
  type EventFixtureSlot,
  type MatchResponse,
  type PlayerEventFixtureItem,
} from '../api/client'

export default function PlayerDashboard() {
  return (
    <ProtectedRoute roles={['PLAYER']}>
      <Layout>
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-white">Dashboard</h2>

          <div>
            <h3 className="text-lg font-semibold text-white mb-4">Match Confirmations</h3>
            <PendingMatchConfirmations />
          </div>

          <div className="border-t border-gray-800 pt-6">
            <h3 className="text-lg font-semibold text-white mb-4">Event Fixtures</h3>
            <PlayerFixtures />
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
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
                disabled={confirmMutation.isPending}>
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

function PlayerFixtures() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [activeEvent, setActiveEvent] = useState<PlayerEventFixtureItem | null>(null)
  const [activeSlot, setActiveSlot] = useState<EventFixtureSlot | null>(null)

  const fixturesQuery = useQuery({
    queryKey: ['player-fixtures', user?.player_id],
    queryFn: () => playersApi.fixtures(user!.player_id!),
    enabled: user?.role === 'PLAYER' && !!user?.player_id,
  })

  if (user?.role !== 'PLAYER') {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-sm text-gray-300">
        Fixture viewing and result entry is only available for PLAYER accounts.
      </div>
    )
  }

  if (!user?.player_id) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-sm text-gray-300">
        Link a player profile to view your upcoming fixtures and submit match results.
      </div>
    )
  }

  const fixtures = fixturesQuery.data?.items ?? []
  const errorMessage = fixturesQuery.error instanceof Error ? fixturesQuery.error.message : 'Unable to load fixtures.'

  const handleSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['player-fixtures', user.player_id] })
    queryClient.invalidateQueries({ queryKey: ['pending-matches'] })
    setActiveSlot(null)
    setActiveEvent(null)
  }

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
        <div className="text-sm text-white font-semibold">My fixtures & matches</div>
        <div className="text-xs text-gray-400">View upcoming event fixtures and submit results for matches you played.</div>
      </div>

      {fixturesQuery.isLoading && <div className="text-sm text-gray-400">Loading fixtures…</div>}
      {fixturesQuery.isError && (
        <div className="bg-red-900/40 border border-red-700 rounded-xl p-4 text-sm text-red-200">{errorMessage}</div>
      )}
      {!fixturesQuery.isLoading && fixtures.length === 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-sm text-gray-300">
          No upcoming event fixtures are available for your player profile.
        </div>
      )}

      {fixtures.map(event => (
        <div key={event.event_id} className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm text-white font-semibold">{event.name}</div>
              <div className="text-xs text-gray-400">
                {event.status} · {event.scheduling_mode.replace(/_/g, ' ')} · {event.event_type.replace(/_/g, ' ')}
              </div>
            </div>
            <div className="text-xs text-gray-400 text-right">
              {event.fixture_state ? `Fixture state: ${event.fixture_state}` : 'No fixture lifecycle'}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-3 text-xs text-gray-400">
              <div>Event dates</div>
              <div className="text-white text-sm">
                {new Date(event.start_date).toLocaleDateString()} — {event.end_date ? new Date(event.end_date).toLocaleDateString() : 'TBD'}
              </div>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/40 p-3 text-xs text-gray-400">
              <div>Default match format</div>
              <div className="text-white text-sm">{event.default_match_format ?? 'BEST_OF_3'}</div>
            </div>
          </div>

          {event.slots.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-700 bg-gray-950/30 p-4 text-sm text-gray-300">
              No fixture slots assigned for this event yet.
            </div>
          ) : (
            <div className="space-y-3">
              {event.slots.map(slot => {
                const isMyA = slot.player_a.player_id === user.player_id
                const opponent = isMyA ? slot.player_b : slot.player_a
                const canSubmit = !slot.match_id && slot.status === 'SCHEDULED' && opponent
                return (
                  <div key={slot.slot_id} className="rounded-xl border border-gray-800 bg-gray-950/30 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <div className="text-sm text-white font-semibold">
                          {isMyA ? slot.player_a.name : slot.player_b?.name} vs {opponent?.name ?? 'Bye'}
                        </div>
                        <div className="text-xs text-gray-400">
                          Round {slot.round_number}, Table {slot.table_number} · {slot.round_intent || slot.gap_band || slot.match_category}
                        </div>
                      </div>
                      <div className="text-right space-y-1 text-xs text-gray-400">
                        <div>{slot.status}</div>
                        {slot.match_id ? <div className="text-green-400">Result submitted</div> : null}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-400">
                      <div>{isMyA ? 'You are Player A' : 'You are Player B'}</div>
                      {opponent ? <div>Opponent: {opponent.name}</div> : <div>Bye / no opponent</div>}
                    </div>
                    {canSubmit && (
                      <div className="pt-3">
                        <button type="button" onClick={() => { setActiveEvent(event); setActiveSlot(slot) }}
                          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-500">
                          Submit result
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ))}

      {activeSlot && activeEvent && (
        <FixtureResultModal
          slot={activeSlot}
          event={activeEvent}
          onClose={() => { setActiveSlot(null); setActiveEvent(null) }}
          onSuccess={handleSuccess}
        />
      )}
    </div>
  )
}

function FixtureResultModal({
  slot,
  event,
  onClose,
  onSuccess,
}: {
  slot: EventFixtureSlot
  event: PlayerEventFixtureItem
  onClose: () => void
  onSuccess: () => void
}) {
  const [setsA, setSetsA] = useState('')
  const [setsB, setSetsB] = useState('')
  const [isRetirement, setIsRetirement] = useState(false)
  const [matchDate] = useState(event.start_date)
  const [error, setError] = useState<string | null>(null)

  const matchFormat = event.default_match_format ?? 'BEST_OF_3'
  const maxSets = matchFormat === 'BEST_OF_1'
    ? 1
    : matchFormat === 'BEST_OF_3'
      ? 2
      : matchFormat === 'BEST_OF_5'
        ? 3
        : 4
  const winnerSets = Number(setsA) > Number(setsB) ? Number(setsA) : Number(setsB)
  const loserSets = Number(setsA) <= Number(setsB) ? Number(setsA) : Number(setsB)
  const isValid = setsA !== '' && setsB !== '' && Number(setsA) !== Number(setsB) && (
    isRetirement
      ? Number(setsA) + Number(setsB) > 0 && Number(setsA) <= maxSets && Number(setsB) <= maxSets
      : winnerSets === maxSets && loserSets < maxSets
  )

  const mutation = useMutation({
    mutationFn: async () => {
      if (!slot.player_b) {
        throw new Error('Cannot submit a bye match result.')
      }
      return matchesApi.submit({
        event_id: event.event_id,
        player_a_id: slot.player_a.player_id,
        player_b_id: slot.player_b.player_id,
        fixture_slot_id: slot.slot_id,
        match_format: matchFormat,
        sets_won_a: Number(setsA),
        sets_won_b: Number(setsB),
        is_retirement: isRetirement,
        match_date: matchDate,
      })
    },
    onSuccess: () => {
      setError(null)
      onSuccess()
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-gray-950 border border-gray-800 p-6 shadow-xl">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <div className="text-lg font-semibold text-white">Submit fixture result</div>
            <div className="text-sm text-gray-400">{event.name}</div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">Close</button>
        </div>

        {error && <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-xl p-4 mb-4 text-sm">{error}</div>}

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-xs text-gray-400">Player A sets</label>
            <input value={setsA} onChange={e => setSetsA(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-white text-sm" />
          </div>
          <div>
            <label className="text-xs text-gray-400">Player B sets</label>
            <input value={setsB} onChange={e => setSetsB(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-white text-sm" />
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <input id="retirement" type="checkbox" checked={isRetirement} onChange={e => setIsRetirement(e.target.checked)} className="rounded border-gray-600 bg-gray-800 text-blue-500" />
            <label htmlFor="retirement">Retirement</label>
          </div>
          <div className="text-sm text-gray-400">Must submit a valid score for the selected match format.</div>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:border-gray-500">Cancel</button>
          <button type="button" onClick={() => mutation.mutate()} disabled={!isValid || mutation.isPending} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50">
            {mutation.isPending ? 'Submitting…' : 'Submit result'}
          </button>
        </div>
      </div>
    </div>
  )
}
