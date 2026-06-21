import React, { useState, useEffect } from 'react'

interface SetPointsInputProps {
  matchFormat: 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7'
  setsWonA: number
  setsWonB: number
  onSetScoresChange: (scores: Array<{ points_a: number; points_b: number }> | null) => void
  isRetirement: boolean
  initialScores?: Array<{ points_a: number; points_b: number }> | null
}

interface LocalSetScore {
  points_a: string
  points_b: string
}

interface ValidationError {
  setIndex: number
  message: string
}

/**
 * SetPointsInput Component
 * 
 * Allows coaches to optionally enter per-set point scores for a match.
 * - Collapsed by default to avoid friction during quick casual entry
 * - Shows validation errors only on Save
 * - Only displays fields for sets that were actually played
 * - Allows coaches to discard all points and submit with just set scores
 */
export const SetPointsInput: React.FC<SetPointsInputProps> = ({
  matchFormat,
  setsWonA,
  setsWonB,
  onSetScoresChange,
  isRetirement,
  initialScores,
}) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [setScores, setSetScores] = useState<LocalSetScore[]>([])
  const [errors, setErrors] = useState<ValidationError[]>([])

  const totalSets = setsWonA + setsWonB
  const maxSetsAllowed = ({ BEST_OF_3: 3, BEST_OF_5: 5, BEST_OF_7: 7 } as const)[matchFormat]

  const isScoreEmpty = (score: LocalSetScore) =>
    score.points_a.trim() === '' && score.points_b.trim() === ''

  const isScorePartiallyFilled = (score: LocalSetScore) =>
    (score.points_a.trim() === '') !== (score.points_b.trim() === '')

  const parseScore = (score: LocalSetScore) => ({
    points_a: Number(score.points_a),
    points_b: Number(score.points_b),
  })

  const countWinningSets = (scores: LocalSetScore[]) => {
    return scores.reduce(
      (acc, score) => {
        if (!isScoreEmpty(score)) {
          const { points_a, points_b } = parseScore(score)
          if (points_a > points_b) acc.winsA += 1
          if (points_b > points_a) acc.winsB += 1
        }
        return acc
      },
      { winsA: 0, winsB: 0 }
    )
  }

  // Initialize empty scores whenever sets change, or seed from provided initialScores.
  useEffect(() => {
    if (initialScores && initialScores.length > 0) {
      const seededScores: LocalSetScore[] = Array(totalSets)
        .fill(null)
        .map((_, idx) => {
          const score = initialScores[idx]
          return {
            points_a: score ? String(score.points_a) : '',
            points_b: score ? String(score.points_b) : '',
          }
        })
      setSetScores(seededScores)
      setIsExpanded(true)
    } else {
      const emptyScores: LocalSetScore[] = Array(totalSets)
        .fill(null)
        .map(() => ({ points_a: '', points_b: '' }))
      setSetScores(emptyScores)
      setIsExpanded(false)
    }
    setErrors([])
  }, [matchFormat, setsWonA, setsWonB, initialScores])

  /**
   * Validate a single set score according to table tennis rules.
   */
  const validateSetScore = (score: LocalSetScore, index: number): ValidationError | null => {
    if (isScoreEmpty(score)) {
      return null
    }

    if (isScorePartiallyFilled(score)) {
      return { setIndex: index, message: 'Both players must have points for this set' }
    }

    const { points_a, points_b } = parseScore(score)

    if (Number.isNaN(points_a) || Number.isNaN(points_b)) {
      return { setIndex: index, message: 'Invalid point value' }
    }

    if (points_a < 0 || points_b < 0) {
      return { setIndex: index, message: 'Points cannot be negative' }
    }

    if (points_a > 30 || points_b > 30) {
      return { setIndex: index, message: 'Points cannot exceed 30' }
    }

    if (points_a === points_b) {
      return { setIndex: index, message: 'Sets cannot end in a tie' }
    }

    const winner = Math.max(points_a, points_b)
    const loser = Math.min(points_a, points_b)

    if (winner < 11) {
      return { setIndex: index, message: 'Winner must have ≥11 points' }
    }

    if (winner === 11) {
      if (loser >= 10) {
        return { setIndex: index, message: 'Invalid point spread' }
      }
      return null
    }

    // Extended deuce scoring: winner must win by exactly 2 points
    if (winner > 11) {
      if (loser !== winner - 2) {
        return { setIndex: index, message: 'Invalid point spread' }
      }
    }

    return null
  }

  /**
   * Update a single set's point value.
   */
  const updateSetScore = (setIndex: number, field: 'a' | 'b', value: string) => {
    const newScores = [...setScores]
    if (field === 'a') {
      newScores[setIndex].points_a = value
    } else {
      newScores[setIndex].points_b = value
    }

    setSetScores(newScores)
    if (errors.length > 0) {
      setErrors([])
    }
  }

  /**
   * Clear all point scores and notify parent.
   */
  const handleClearPoints = () => {
    const emptyScores: LocalSetScore[] = Array(totalSets)
      .fill(null)
      .map(() => ({ points_a: '', points_b: '' }))
    setSetScores(emptyScores)
    setErrors([])
    onSetScoresChange(null) // Signal to parent: no points submitted
  }

  const handleKeepPoints = () => {
    const allEmptyScores = setScores.every(isScoreEmpty)
    if (allEmptyScores) {
      // All scores empty - discard
      handleClearPoints()
      return
    }

    // Check if any score is partially filled
    const partiallyFilled = setScores.some(isScorePartiallyFilled)
    if (partiallyFilled) {
      setErrors([
        {
          setIndex: -1,
          message: 'All sets must have both players\' points or be completely empty',
        },
      ])
      return
    }

    // Validate all scores
    const newErrors: ValidationError[] = []
    setScores.forEach((score, idx) => {
      const error = validateSetScore(score, idx)
      if (error) {
        newErrors.push(error)
      }
    })

    if (newErrors.length > 0) {
      setErrors(newErrors)
      return
    }

    const { winsA, winsB } = countWinningSets(setScores)
    if (winsA !== setsWonA || winsB !== setsWonB) {
      setErrors([
        {
          setIndex: -1,
          message: `Game points must match the entered set score (${setsWonA}-${setsWonB})`,
        },
      ])
      return
    }

    // All valid - submit only played set scores
    onSetScoresChange(
      setScores
        .filter(score => !isScoreEmpty(score))
        .map(parseScore)
    )
    setIsExpanded(false)
  }

  // Only show optional game-point entry once set totals are available and valid.
  if (totalSets === 0 || totalSets > maxSetsAllowed) {
    return null
  }

  return (
    <div className="set-points-input">
      {/* Toggle Button */}
      <button
        type="button"
        className="set-points-toggle"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-controls="set-points-detail"
      >
        <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
        <span className="toggle-text">Set game points (optional)</span>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div id="set-points-detail" className="set-points-detail">
          {isRetirement && (
            <div className="retirement-hint">
              Retirement matches may omit point details, but you may still enter them if available.
            </div>
          )}
          <div className="set-points-container">
            {setScores.map((score, idx) => (
                <div key={idx} className="set-points-row">
                  <label htmlFor={`set-${idx}-a`} className="set-label">
                    Set {idx + 1}:
                  </label>
                  <input
                    id={`set-${idx}-a`}
                    type="number"
                    min={0}
                    max={30}
                    value={score.points_a}
                    onChange={(e) => updateSetScore(idx, 'a', e.target.value)}
                    placeholder="0"
                    className="points-input"
                    aria-label={`Set ${idx + 1} Player A points`}
                  />
                  <span className="separator">-</span>
                  <input
                    id={`set-${idx}-b`}
                    type="number"
                    min={0}
                    max={30}
                    value={score.points_b}
                    onChange={(e) => updateSetScore(idx, 'b', e.target.value)}
                    placeholder="0"
                    className="points-input"
                    aria-label={`Set ${idx + 1} Player B points`}
                  />
                </div>
              ))}
            </div>

          {/* Error Messages */}
          {errors.length > 0 && (
            <div className="error-messages" role="alert" aria-live="polite">
              {errors.map((err, i) =>
                err.setIndex === -1 ? (
                  <div key={i} className="error-item error-general">
                    {err.message}
                  </div>
                ) : (
                  <div key={i} className="error-item">
                    Set {err.setIndex + 1}: {err.message}
                  </div>
                )
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div className="button-group">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClearPoints}
            >
              Discard Points
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleKeepPoints}
            >
              Save Points
            </button>
          </div>
        </div>
      )}

      <style>{`
        .set-points-input {
          margin: 1rem 0;
          border: 1px solid #e0e0e0;
          border-radius: 4px;
          background-color: #f9f9f9;
        }

        .set-points-toggle {
          width: 100%;
          padding: 0.75rem 1rem;
          background: #0f172a;
          border: 1px solid #334155;
          border-radius: 0.5rem;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.95rem;
          font-weight: 500;
          color: #f8fafc;
          text-align: left;
          transition: background-color 0.2s;
        }

        .set-points-toggle:hover {
          background-color: #111827;
        }

        .toggle-icon {
          flex-shrink: 0;
          font-size: 0.8rem;
        }

        .toggle-text {
          flex: 1;
        }

        .toggle-hint {
          font-size: 0.8rem;
          color: #999;
          font-weight: normal;
        }

        .set-points-detail {
          padding: 1rem;
          border-top: 1px solid #334155;
          background-color: #0b1120;
        }

        .retirement-hint {
          margin-bottom: 0.75rem;
          padding: 0.65rem 0.75rem;
          border-radius: 4px;
          background-color: #111827;
          color: #e2e8f0;
          font-size: 0.9rem;
          border: 1px solid #334155;
        }

        .info-hint {
          margin-bottom: 0.75rem;
          padding: 0.8rem 0.9rem;
          border-radius: 4px;
          background-color: #111827;
          color: #cbd5e1;
          font-size: 0.92rem;
          border: 1px solid #334155;
        }

        .set-points-container {
          display: grid;
          gap: 0.75rem;
          margin-bottom: 1rem;
        }

        .set-points-row {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .set-label {
          min-width: 50px;
          font-weight: 500;
          font-size: 0.95rem;
        }

        .points-input {
          width: 60px;
          padding: 0.4rem;
          border: 1px solid #94a3b8;
          border-radius: 3px;
          font-size: 0.95rem;
          text-align: center;
          background-color: #f8fafc;
          color: #0f172a;
        }

        .points-input:focus {
          outline: none;
          border-color: #2563eb;
          box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
        }

        .separator {
          margin: 0 0.25rem;
          color: #666;
        }

        .error-messages {
          background-color: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 3px;
          padding: 0.75rem;
          margin-bottom: 1rem;
        }

        .error-item {
          font-size: 0.9rem;
          color: #dc2626;
          margin-bottom: 0.25rem;
        }

        .error-item:last-child {
          margin-bottom: 0;
        }

        .error-general {
          font-weight: 500;
        }

        .button-group {
          display: flex;
          gap: 0.75rem;
          justify-content: flex-end;
        }

        .btn {
          padding: 0.5rem 1rem;
          border: none;
          border-radius: 3px;
          font-size: 0.95rem;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .btn-secondary {
          background-color: #e5e7eb;
          color: #374151;
        }

        .btn-secondary:hover {
          background-color: #d1d5db;
        }

        .btn-primary {
          background-color: #2563eb;
          color: white;
        }

        .btn-primary:hover {
          background-color: #1d4ed8;
        }

        .btn-primary:disabled {
          background-color: #bfdbfe;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  )
}
