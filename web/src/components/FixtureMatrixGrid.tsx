import { useState } from 'react'
import type { MatrixModel, LegendItem, MatrixCell } from '../lib/fixtures'
import { getFirstName, getOpponentLabel } from '../lib/fixtures'

export default function FixtureMatrixGrid({
  model,
  legend,
  sectionFilter = true,
  dimCategory = null,
  onCellClick,
}: {
  model: MatrixModel
  legend: LegendItem[]
  sectionFilter?: boolean
  dimCategory?: string | null
  onCellClick?: (cell: MatrixCell) => void
}) {
  const [filterSectionId, setFilterSectionId] = useState<string | null>(null)
  const [highlightRound, setHighlightRound] = useState<number | null>(null)

  const firstNameCounts = Object.values(model.sections).flatMap((s: any) => s.players).reduce<Record<string, number>>((acc, p: any) => {
    const first = getFirstName(p.name)
    acc[first] = (acc[first] ?? 0) + 1
    return acc
  }, {})

  const rounds = model.rounds

  // Build a flattened, discriminated rows list that respects filterSectionId
  const rows: Array<any> = model.sections.flatMap((section: any) => {
    if (filterSectionId && filterSectionId !== section.id) return []
    if (model.sections.length === 1) {
      return section.players.map((p: any) => ({ kind: 'player', section, player: p }))
    }
    return [{ kind: 'header', section }, ...section.players.map((p: any) => ({ kind: 'player', section, player: p }))]
  })

  const renderPlayerRow = (section: any, p: any) => {
    const playerId = p.player_id
    const playerRating = Math.round(p.current_rating)
    return (
      <tr key={playerId} className="hover:bg-gray-800/20 transition-colors">
        <td className="text-left px-3 py-1.5 border-b border-gray-800 sticky left-0 bg-gray-900/40 min-w-[150px] z-10">
          <div className={`font-medium truncate ${section.accent.text}`}>{p.name}</div>
          <div className="text-[10px] text-gray-500">{section.label}</div>
        </td>
        <td className="text-right px-2 py-1.5 border-b border-gray-800 font-mono text-[10px] text-gray-400">{playerRating}</td>
        {rounds.map((r: number) => {
          const cell: MatrixCell | undefined = model.schedule[p.player_id]?.[r]
          const isBye = cell?.isBye ?? false
          const isHighlighted = r === highlightRound
          const cellCategory = isBye ? 'bye' : (cell?.category ?? 'competitive')
          const shouldDim = dimCategory != null && cellCategory !== dimCategory
          return (
            <td key={r} className={`relative text-center px-1.5 py-1.5 border-b border-gray-800 ${isHighlighted ? 'bg-yellow-900/40' : ''} ${cell?.match_id ? 'cursor-pointer hover:bg-gray-800/70' : ''}`}
              title={cell?.tooltip ?? (isBye ? 'BYE' : 'No opponent')}
              onClick={() => cell?.match_id && onCellClick?.(cell)}>
              {isBye ? (
                <span className={`text-[10px] text-gray-600 font-medium ${shouldDim ? 'opacity-30' : ''}`}>BYE</span>
              ) : cell?.opponent ? (
                <div className={`relative min-h-[32px] ${shouldDim ? 'opacity-30' : ''}`}>
                  <div className={`text-xs font-semibold truncate text-gray-200`}>{getOpponentLabel(cell.opponent, firstNameCounts)}</div>
                  <div className="text-[9px] text-gray-500 mt-0.5">{Math.round(cell.opponent.current_rating)}</div>
                  <span className={`absolute bottom-0 left-1 right-1 h-[2px] rounded-sm ${cell.stripClass}`} />
                </div>
              ) : (
                <span className={`text-gray-600 ${shouldDim ? 'opacity-30' : ''}`}>—</span>
              )}
            </td>
          )
        })}
      </tr>
    )
  }

  return (
    <div className="space-y-3">
      {sectionFilter && (
        <div className="flex gap-1.5 flex-wrap">
          <button onClick={() => setFilterSectionId(null)}
            className={`px-2 py-1 text-xs rounded transition-colors ${!filterSectionId ? 'bg-white text-gray-900 font-medium' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
            All
          </button>
          {model.sections.map((s: any) => (
            <button key={s.id} onClick={() => setFilterSectionId(filterSectionId === s.id ? null : s.id)}
              className={`px-2 py-1 text-xs rounded transition-colors ${filterSectionId === s.id ? `${s.accent.bg} ${s.accent.text} font-medium` : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
              {s.label}
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-gray-400 uppercase tracking-wide">Legend:</span>
        {legend.map(item => (
          <span key={item.label} className="inline-flex items-center gap-2 rounded-full bg-gray-900/70 px-2 py-1">
            <span className={`w-2.5 h-2.5 rounded-full ${item.bg}`} />
            <span className={`text-xs font-semibold text-gray-200`}>{item.label}</span>
          </span>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-800 w-fit max-w-full">
        <table className="table-fixed text-xs border-collapse">
          <colgroup>
            <col style={{ width: '150px' }} />
            <col style={{ width: '60px' }} />
            {rounds.map((r: number) => (
              <col key={r} style={{ width: '70px' }} />
            ))}
          </colgroup>
          <thead>
            <tr className="bg-gray-900/80">
              <th className="text-left px-3 py-2 text-gray-500 border-b border-gray-800 sticky left-0 bg-gray-900 min-w-[150px] z-10">Player</th>
              <th className="text-right px-2 py-2 text-gray-500 border-b border-gray-800">Rtg</th>
              {rounds.map((r: number, i: number) => (
                <th key={r} onClick={() => setHighlightRound(highlightRound === r ? null : r)}
                  className="text-center px-1.5 py-2 text-gray-600 border-b border-gray-800 cursor-pointer hover:bg-gray-800/50"
                  title={`Round ${i + 1}`}>
                  R{i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              if (row.kind === 'header') {
                const section = row.section
                return (
                  <tr key={`header-${section.id}`} className="border-b border-gray-800 last:border-0 bg-gray-950/40">
                    <td colSpan={rounds.length + 2} className="text-xs uppercase tracking-wider font-bold text-gray-400 px-3 py-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`w-1.5 h-3 rounded-sm ${section.accent.bg}`} />
                        {section.label}
                      </div>
                    </td>
                  </tr>
                )
              }
              return renderPlayerRow(row.section, row.player)
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
