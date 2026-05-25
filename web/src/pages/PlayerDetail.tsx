import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { playersApi } from '../api/client'
import { Layout, Spinner, ErrorMsg } from '../components/Layout'
import { useAuth } from '../auth/context'
import { PlayerHeader, VelocitySection, MatchHistory, type ChartPoint } from '../components/PlayerDetailParts'

// PERIODS moved to PlayerDetailParts

// helper functions and UI parts moved to components/PlayerDetailParts.tsx

// ── Component ─────────────────────────────────────────────────────────────────

export default function PlayerDetail() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [period, setPeriod] = useState<'1m' | '3m' | '6m' | '1y'>('3m')
  const [historyTab, setHistoryTab] = useState<'session' | 'timeline'>('session')
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set())
  const [expandedBreakdowns, setExpandedBreakdowns] = useState<Set<string>>(new Set())

  function toggleSession(key: string) {
    setExpandedSessions(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function toggleBreakdown(historyId: string) {
    setExpandedBreakdowns(prev => {
      const next = new Set(prev)
      next.has(historyId) ? next.delete(historyId) : next.add(historyId)
      return next
    })
  }

  const playerQ = useQuery({
    queryKey: ['player', id],
    queryFn: () => playersApi.get(id!),
    enabled: !!id,
  })

  const statsQ = useQuery({
    queryKey: ['player', id, 'stats'],
    queryFn: () => playersApi.computedStats(id!),
    enabled: !!id,
  })

  const historyQ = useQuery({
    queryKey: ['player', id, 'history'],
    queryFn: () => playersApi.ratingHistory(id!, { limit: 200 }),
    enabled: !!id,
  })

  const velocityQ = useQuery({
    queryKey: ['player', id, 'velocity', period],
    queryFn: () => playersApi.velocity(id!, period),
    enabled: !!id,
  })

  const p = playerQ.data
  const s = statsQ.data
  const h = historyQ.data
  const v = velocityQ.data

  if (playerQ.isLoading) return <Layout><Spinner /></Layout>
  if (playerQ.error) return <Layout><ErrorMsg message={(playerQ.error as Error).message} /></Layout>
  if (!p) return null

  const isSelf = user?.user_id === id
  const canSeeBreakdown = isSelf || user?.role === 'COACH' || user?.role === 'ADMIN'

  const sortedItems = h?.items.slice().reverse() // oldest-first after backend DESC order
  const chartData = sortedItems && sortedItems.length > 0
    ? [
        {
          seq: 0,
          date: (sortedItems[0].match_date ?? sortedItems[0].created_at ?? '').slice(0, 10),
          rating: Math.round(sortedItems[0].rating_before),
        },
        ...sortedItems.map((r, i) => ({
          seq: i + 1,
          date: (r.match_date ?? r.created_at ?? '').slice(0, 10),
          rating: Math.round(r.rating_after),
        })),
      ]
    : undefined

  return (
    <Layout>
      <div className="space-y-6">
        <PlayerHeader player={p} stats={s} canSeeBreakdown={canSeeBreakdown} />
        <VelocitySection period={period} setPeriod={setPeriod} isLoading={velocityQ.isLoading} velocity={v} chartData={chartData as ChartPoint[] | undefined} />
        <MatchHistory history={h} historyTab={historyTab} setHistoryTab={setHistoryTab} expandedSessions={expandedSessions} toggleSession={toggleSession} expandedBreakdowns={expandedBreakdowns} toggleBreakdown={toggleBreakdown} canSeeBreakdown={canSeeBreakdown} />
      </div>
    </Layout>
  )
}

