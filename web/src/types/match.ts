/**
 * Match-related TypeScript types and interfaces.
 * Provides type safety for match submission and display workflows.
 */

/**
 * Per-set point score entry.
 * Used when coaches optionally enter individual game points.
 */
export interface SetScore {
  set_number: number
  points_a: number
  points_b: number
}

/**
 * Match submission form data.
 * Includes required set results and optional per-set points.
 */
export interface MatchSubmitData {
  event_id: string
  session_id?: string | null
  fixture_slot_id?: string | null
  player_a_id: string
  player_b_id: string
  match_format: 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7'
  sets_won_a: number
  sets_won_b: number
  sets_won_a_actual?: number | null
  sets_won_b_actual?: number | null
  is_retirement: boolean
  match_date: string
  set_scores?: Array<{ points_a: number; points_b: number }> | null
}

/**
 * Match result response from API.
 * Includes all match data and optional per-set point breakdown.
 */
export interface MatchResultData {
  match_id: string
  event_id: string
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
  ratings_applied_at?: string | null
  ratings_trigger?: string
  match_date: string
  match_timestamp?: string
  created_at?: string
  set_scores?: SetScore[] | null
}
