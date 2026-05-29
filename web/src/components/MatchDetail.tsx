import React from 'react'
import type { SetScore } from '../api/client'

interface MatchDetailProps {
  match: {
    match_id: string
    event_id: string
    round_intent?: string | null
    gap_band?: string | null
    player_a_role?: string | null
    player_b_role?: string | null
    player_a: { player_id: string; name: string; current_rating: number }
    player_b: { player_id: string; name: string; current_rating: number }
    sets_won_a: number
    sets_won_b: number
    sets_won_a_actual?: number | null
    sets_won_b_actual?: number | null
    match_format: string
    is_retirement: boolean
    winner_id: string
    rating_eligible: boolean
    not_eligible_reason?: string | null
    confirmation_status: string
    confirmation_deadline: string
    match_date: string
    set_scores?: SetScore[] | null
  }
}

/**
 * MatchDetail Component
 *
 * Displays a match result with optional point-by-point breakdown.
 * Shows:
 * - Match summary (player names, set scores)
 * - Per-set point scores if available
 * - Confirmation status and metadata
 */
export const MatchDetail: React.FC<MatchDetailProps> = ({ match }) => {
  const getResultText = (): string => {
    if (match.is_retirement) {
      return 'Retirement'
    }
    return match.sets_won_a > match.sets_won_b ? `${match.player_a.name} won` : `${match.player_b.name} won`
  }

  const formatConfirmationStatus = (status: string): string => {
    switch (status) {
      case 'CONFIRMED':
        return 'Confirmed'
      case 'PENDING':
        return 'Pending Confirmation'
      case 'DISPUTED':
        return 'Disputed'
      case 'VOIDED':
        return 'Voided'
      default:
        return status
    }
  }

  return (
    <div className="match-detail">
      <div className="match-header">
        <h2 className="match-title">Match Result</h2>
        <div className={`status status-${match.confirmation_status.toLowerCase()}`}>
          {formatConfirmationStatus(match.confirmation_status)}
        </div>
      </div>

      <div className="result-summary">
        <div className="player player-a">
          <div className="player-name">{match.player_a.name}</div>
          <div className="player-rating">Rating: {match.player_a.current_rating}</div>
        </div>

        <div className="result">
          <div className="sets-score">
            {match.sets_won_a} - {match.sets_won_b}
          </div>
          <div className="result-text">{getResultText()}</div>
        </div>

        <div className="player player-b">
          <div className="player-name">{match.player_b.name}</div>
          <div className="player-rating">Rating: {match.player_b.current_rating}</div>
        </div>
      </div>

      {/* Point Breakdown - Only show if points were recorded */}
      {match.set_scores && match.set_scores.length > 0 && (
        <div className="point-details">
          <h3 className="detail-heading">Point Breakdown</h3>
          <div className="sets-list">
            {match.set_scores.map((score) => (
              <div key={score.set_number} className="set-result">
                <div className="set-number">Set {score.set_number}</div>
                <div className="set-points">
                  <span className={`points ${score.points_a > score.points_b ? 'winner' : ''}`}>
                    {score.points_a}
                  </span>
                  <span className="separator">-</span>
                  <span className={`points ${score.points_b > score.points_a ? 'winner' : ''}`}>
                    {score.points_b}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Match Metadata */}
      <div className="match-metadata">
        <div className="metadata-grid">
          <div className="metadata-item">
            <div className="metadata-label">Match Date</div>
            <div className="metadata-value">{new Date(match.match_date).toLocaleDateString()}</div>
          </div>

          <div className="metadata-item">
            <div className="metadata-label">Format</div>
            <div className="metadata-value">{match.match_format}</div>
          </div>

          {match.round_intent && (
            <div className="metadata-item">
              <div className="metadata-label">Round Intent</div>
              <div className="metadata-value">{match.round_intent}</div>
            </div>
          )}
          {match.gap_band && (
            <div className="metadata-item">
              <div className="metadata-label">Gap Band</div>
              <div className="metadata-value">{match.gap_band.replace(/_/g, ' ')}</div>
            </div>
          )}
          {match.player_a_role && (
            <div className="metadata-item">
              <div className="metadata-label">Player A role</div>
              <div className="metadata-value">{match.player_a_role.replace(/_/g, ' ')}</div>
            </div>
          )}
          {match.player_b_role && (
            <div className="metadata-item">
              <div className="metadata-label">Player B role</div>
              <div className="metadata-value">{match.player_b_role.replace(/_/g, ' ')}</div>
            </div>
          )}

          <div className="metadata-item">
            <div className="metadata-label">Rating Eligible</div>
            <div className="metadata-value">
              {match.rating_eligible ? (
                <span className="badge badge-success">Yes</span>
              ) : (
                <span className="badge badge-warning">No</span>
              )}
              {match.not_eligible_reason && (
                <div className="reason">({match.not_eligible_reason})</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .match-detail {
          background: white;
          border-radius: 6px;
          padding: 1.5rem;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .match-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
          border-bottom: 2px solid #e5e7eb;
          padding-bottom: 1rem;
        }

        .match-title {
          margin: 0;
          font-size: 1.5rem;
          font-weight: 600;
          color: #111;
        }

        .status {
          padding: 0.5rem 0.75rem;
          border-radius: 3px;
          font-size: 0.85rem;
          font-weight: 600;
          text-transform: uppercase;
        }

        .status-confirmed {
          background-color: #dcfce7;
          color: #166534;
        }

        .status-pending {
          background-color: #fef3c7;
          color: #92400e;
        }

        .status-disputed {
          background-color: #fee2e2;
          color: #991b1b;
        }

        .status-voided {
          background-color: #e5e7eb;
          color: #374151;
        }

        .result-summary {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 2rem;
          margin-bottom: 2rem;
          padding: 1.5rem;
          background-color: #f9fafb;
          border-radius: 4px;
        }

        .player {
          flex: 1;
          text-align: center;
        }

        .player-name {
          font-size: 1.1rem;
          font-weight: 600;
          color: #111;
          margin-bottom: 0.5rem;
        }

        .player-rating {
          font-size: 0.9rem;
          color: #666;
        }

        .result {
          flex: 0 0 auto;
          text-align: center;
        }

        .sets-score {
          font-size: 2.5rem;
          font-weight: 700;
          color: #2563eb;
          letter-spacing: 0.05em;
        }

        .result-text {
          font-size: 0.9rem;
          color: #666;
          margin-top: 0.5rem;
        }

        .point-details {
          margin: 2rem 0;
          padding: 1rem;
          background-color: #f3f4f6;
          border-radius: 4px;
        }

        .detail-heading {
          margin: 0 0 1rem 0;
          font-size: 1rem;
          font-weight: 600;
          color: #111;
        }

        .sets-list {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
          gap: 0.75rem;
        }

        .set-result {
          background: white;
          padding: 0.75rem;
          border-radius: 3px;
          text-align: center;
          border: 1px solid #e5e7eb;
        }

        .set-number {
          font-size: 0.85rem;
          color: #666;
          font-weight: 500;
          margin-bottom: 0.5rem;
        }

        .set-points {
          font-size: 1.1rem;
          font-weight: 600;
        }

        .points {
          display: inline-block;
          width: 40px;
          padding: 0.25rem;
        }

        .points.winner {
          color: #059669;
          font-weight: 700;
        }

        .separator {
          margin: 0 0.25rem;
          color: #999;
        }

        .match-metadata {
          margin-top: 2rem;
          padding-top: 1.5rem;
          border-top: 1px solid #e5e7eb;
        }

        .metadata-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 1rem;
        }

        .metadata-item {
          padding: 0.75rem;
        }

        .metadata-label {
          font-size: 0.85rem;
          font-weight: 600;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 0.5rem;
        }

        .metadata-value {
          font-size: 0.95rem;
          color: #111;
        }

        .reason {
          font-size: 0.8rem;
          color: #666;
          margin-top: 0.25rem;
        }

        .badge {
          display: inline-block;
          padding: 0.25rem 0.5rem;
          border-radius: 2px;
          font-size: 0.8rem;
          font-weight: 600;
          text-transform: uppercase;
        }

        .badge-success {
          background-color: #dcfce7;
          color: #166534;
        }

        .badge-warning {
          background-color: #fef3c7;
          color: #92400e;
        }
      `}</style>
    </div>
  )
}
