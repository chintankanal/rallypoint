import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { leaderboardApi } from '../api/client'
import { Layout, TierBadge, Spinner, ErrorMsg } from '../components/Layout'
import { DominanceCell, TrendCell, WinPctCell, lastActive } from '../lib/leaderboardHelpers'
import { DOMINANCE_HELP } from '../lib/leaderboardCopy'

const TIERS = ['', 'BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'ELITE', 'NATIONAL_TRACK']
const PAGE_SIZE = 25


export default function Leaderboard() {
  const [tier, setTier] = useState('')
  const [offset, setOffset] = useState(0)
  const [ageGroup, setAgeGroup] = useState('')
  const [showDominanceInfo, setShowDominanceInfo] = useState(false)

  const globalQ = useQuery({
    queryKey: ['leaderboard', 'global', tier, offset],
    queryFn: () => leaderboardApi.global({ tier: tier || undefined, limit: PAGE_SIZE, offset }),
    enabled: !ageGroup,
  })

  const ageQ = useQuery({
    queryKey: ['leaderboard', 'age', ageGroup],
    queryFn: () => leaderboardApi.ageGroup(ageGroup),
    enabled: !!ageGroup,
  })

  const isLoading = ageGroup ? ageQ.isLoading : globalQ.isLoading
  const error = ageGroup ? ageQ.error : globalQ.error
  const globalData = globalQ.data
  const ageData = ageQ.data

  return (
    <Layout>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-4">Global Leaderboard</h2>

        <div className="flex flex-wrap gap-3 mb-4">
          <select
            value={tier}
            onChange={e => { setTier(e.target.value); setOffset(0); setAgeGroup('') }}
            className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm"
          >
            {TIERS.map(t => (
              <option key={t} value={t}>{t ? t.replace('_', ' ') : 'All Tiers'}</option>
            ))}
          </select>

          <select
            value={ageGroup}
            onChange={e => { setAgeGroup(e.target.value); setTier(''); setOffset(0) }}
            className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">All Ages</option>
            <option value="U11">U11</option>
            <option value="U13">U13</option>
            <option value="U15">U15</option>
            <option value="U17">U17</option>
            <option value="OPEN">Open</option>
          </select>
        </div>

        {isLoading && <Spinner />}
        {error && <ErrorMsg message={(error as Error).message} />}

        {/* Global leaderboard table */}
        {!ageGroup && globalData && (
          <>
            {showDominanceInfo && (
              <div className="mb-3 rounded-lg border border-gray-700 bg-gray-900 p-3 text-xs text-gray-300">
                <span className="font-semibold text-gray-100">Dominance:</span>
                {DOMINANCE_HELP}
              </div>
            )}
            <div className="overflow-x-auto rounded-xl border border-gray-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-900 text-gray-400 text-left">
                    <th className="px-4 py-3 w-12 whitespace-nowrap sticky left-0 z-20 bg-gray-900">#</th>
                    <th className="px-4 py-3 whitespace-nowrap sticky left-12 z-20 bg-gray-900 border-r border-gray-800">Player</th>
                    <th className="px-4 py-3 whitespace-nowrap">Academy</th>
                    <th className="px-4 py-3 whitespace-nowrap">Rating ↓</th>
                    <th className="px-4 py-3 whitespace-nowrap">Tier</th>
                    <th className="px-4 py-3 whitespace-nowrap">Gender</th>
                    <th className="px-4 py-3 whitespace-nowrap">Age Cat.</th>
                    <th className="px-4 py-3 whitespace-nowrap">Matches ↓</th>
                    <th className="px-4 py-3 whitespace-nowrap">Win %</th>
                    <th className="px-4 py-3 whitespace-nowrap">Trend</th>
                    <th
                      className="px-4 py-3 whitespace-nowrap"
                      title={DOMINANCE_HELP}
                    >
                      <span className="inline-flex items-center gap-1">
                        Dominance
                        <button
                          type="button"
                          aria-label="What is Dominance?"
                          onClick={() => setShowDominanceInfo(v => !v)}
                          className="text-gray-500 hover:text-gray-200"
                        >
                          ⓘ
                        </button>
                      </span>
                    </th>
                    <th className="px-4 py-3 whitespace-nowrap">Last Active</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {globalData.items.map(row => (
                    <tr key={row.player_id} className="hover:bg-gray-900/50 transition-colors">
                      <td className="px-4 py-3 text-gray-500 font-mono sticky left-0 z-10 bg-gray-950">{row.rank}</td>
                      <td className="px-4 py-3 sticky left-12 z-10 bg-gray-950 border-r border-gray-800">
                        <Link to={`/player/${row.player_id}`} className="text-blue-400 hover:text-blue-300 font-medium">
                          {row.name}
                        </Link>
                        {row.is_provisional && (
                          <span className="ml-2 text-yellow-500 text-xs">(P)</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-400">
                        {row.academy_name ?? '—'}
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-white">
                        {Math.round(row.current_rating)}
                      </td>
                      <td className="px-4 py-3">
                        <TierBadge tier={row.tier} />
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">
                        {row.gender === 'MALE' ? 'M' : row.gender === 'FEMALE' ? 'F' : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">
                        {row.age_group ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-400">
                        {row.rated_matches}
                      </td>
                      <WinPctCell row={row} />
                      <TrendCell row={row} />
                      <DominanceCell row={row} />
                      <td className="px-4 py-3 text-gray-400 text-xs">
                        {lastActive(row.last_match_date)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between mt-4 text-sm text-gray-400">
              <span>{globalData.total} players</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0}
                  className="px-3 py-1.5 bg-gray-800 rounded disabled:opacity-40 hover:bg-gray-700 transition-colors"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  disabled={offset + PAGE_SIZE >= globalData.total}
                  className="px-3 py-1.5 bg-gray-800 rounded disabled:opacity-40 hover:bg-gray-700 transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}

        {/* Age group leaderboard table */}
        {ageGroup && ageData && (
          <div className="overflow-x-auto rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-900 text-gray-400 text-left">
                  <th className="px-4 py-3 w-12 whitespace-nowrap sticky left-0 z-20 bg-gray-900">#</th>
                  <th className="px-4 py-3 whitespace-nowrap sticky left-12 z-20 bg-gray-900 border-r border-gray-800">Player</th>
                  <th className="px-4 py-3 whitespace-nowrap">Academy</th>
                  <th className="px-4 py-3 whitespace-nowrap">Rating ↓</th>
                  <th className="px-4 py-3 whitespace-nowrap">Tier</th>
                  <th className="px-4 py-3 whitespace-nowrap">Age</th>
                  <th className="px-4 py-3 whitespace-nowrap">Gender</th>
                  <th className="px-4 py-3 whitespace-nowrap">Percentile</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {ageData.items.map(row => (
                  <tr key={row.player_id} className="hover:bg-gray-900/50 transition-colors">
                    <td className="px-4 py-3 text-gray-500 font-mono sticky left-0 z-10 bg-gray-950">{row.rank}</td>
                    <td className="px-4 py-3 sticky left-12 z-10 bg-gray-950 border-r border-gray-800">
                      <Link to={`/player/${row.player_id}`} className="text-blue-400 hover:text-blue-300 font-medium">
                        {row.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {row.academy_name ?? '—'}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-white">
                      {Math.round(row.current_rating)}
                    </td>
                    <td className="px-4 py-3">
                      <TierBadge tier={row.tier} />
                    </td>
                    <td className="px-4 py-3 text-gray-400">{row.age_jan1}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {row.gender === 'MALE' ? 'M' : row.gender === 'FEMALE' ? 'F' : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {Math.round(row.percentile * 100)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 text-xs text-gray-500">{ageData.total} players in {ageGroup}</div>
          </div>
        )}
      </div>
    </Layout>
  )
}
