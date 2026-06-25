import type { LeaderboardEntry } from '../api/client'

export function lastActive(d: string | null | undefined): string {
  if (!d) return '—'

  const days = Math.floor((Date.now() - new Date(d).getTime()) / 86400000)

  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`

  return `${Math.floor(days / 365)}y ago`
}

export function WinPctCell({ row }: { row: LeaderboardEntry }) {
  return (
    <td className="px-4 py-3 text-gray-400">
      {row.win_pct != null ? `${row.win_pct}%` : '—'}
    </td>
  )
}

export function TrendCell({ row }: { row: LeaderboardEntry }) {
  return (
    <td className="px-4 py-3 font-mono whitespace-nowrap">
      {row.last_rating_change == null ? (
        <span className="text-gray-500">—</span>
      ) : row.last_rating_change > 0 ? (
        <span className="text-emerald-400">▲ +{Math.round(row.last_rating_change)}</span>
      ) : row.last_rating_change < 0 ? (
        <span className="text-red-400">▼ {Math.round(row.last_rating_change)}</span>
      ) : (
        <span className="text-gray-400">0</span>
      )}
    </td>
  )
}

export function DominanceCell({ row }: { row: LeaderboardEntry }) {
  return (
    <td
      className="px-4 py-3 font-mono"
      title={
        row.dominance == null
          ? 'No rated matches yet'
          : row.dominance > 0
            ? `Winning by ~${row.dominance.toFixed(1)} sets per match on average (last ${row.dominance_sample ?? 0}).`
            : row.dominance < 0
              ? `Losing by ~${Math.abs(row.dominance).toFixed(1)} sets per match on average (last ${row.dominance_sample ?? 0}).`
              : `Even on average over the last ${row.dominance_sample ?? 0} match(es).`
      }
    >
      {row.dominance == null ? (
        <span className="text-gray-500">—</span>
      ) : (
        <span
          className={
            row.dominance > 0
              ? 'text-emerald-400'
              : row.dominance < 0
                ? 'text-red-400'
                : 'text-gray-400'
          }
        >
          {row.dominance > 0 ? `+${row.dominance.toFixed(1)}` : row.dominance.toFixed(1)}
        </span>
      )}
    </td>
  )
}
