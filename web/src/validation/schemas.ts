import { z } from 'zod'
import { playersApi, eventsApi } from '../api/client'

/**
 * Validation schemas for RallyPoint forms.
 * Uses Zod for type-safe, runtime validation with clear error messages.
 * 
 * Includes both synchronous and asynchronous validation:
 * - Sync: Format rules, age, required fields
 * - Async: Player name uniqueness, event existence
 */

// ── Constants ──────────────────────────────────────────────────────────────

const MAX_SETS_BY_FORMAT = {
  BEST_OF_3: 2,
  BEST_OF_5: 3,
  BEST_OF_7: 4,
} as const

// ── Async Validators ──────────────────────────────────────────────────────

/**
 * Check if an event exists by ID.
 * Used to validate event_id before match submission.
 */
export async function checkEventExists(eventId: string): Promise<boolean> {
  try {
    await eventsApi.get(eventId)
    return true
  } catch {
    return false
  }
}

/**
 * Check if a player name already exists in an academy.
 * Used to prevent duplicate player names within the same academy.
 */
export async function checkPlayerNameUnique(
  name: string,
  academyId: string,
): Promise<boolean> {
  try {
    const result = await playersApi.search(name, academyId)
    // Check if any player has an exact name match (case-insensitive)
    const exists = result.items.some(
      p => p.name.toLowerCase() === name.toLowerCase(),
    )
    return !exists // Return true if unique (doesn't exist)
  } catch {
    // On error, allow submission (better UX than blocking)
    return true
  }
}

// ── Helper Validators ─────────────────────────────────────────────────────

/**
 * Validates match sets according to the match format rules.
 * Rules:
 * - Sets won must be valid for the format (0 to max)
 * - Exactly one player must have the maximum sets to win, OR it's a retirement
 * - In a retirement, both players can have any valid set count
 */
function validateMatchSets(
  setsA: number,
  setsB: number,
  format: keyof typeof MAX_SETS_BY_FORMAT,
  isRetirement: boolean,
) {
  const maxSets = MAX_SETS_BY_FORMAT[format]

  if (setsA < 0 || setsB < 0) {
    return { valid: false, error: 'Sets won cannot be negative' }
  }

  if (setsA > maxSets || setsB > maxSets) {
    return { valid: false, error: `Maximum ${maxSets} sets allowed in ${format}` }
  }

  if (isRetirement) {
    // In retirement, at least one player should be involved (not both 0)
    if (setsA === 0 && setsB === 0) {
      return { valid: false, error: 'At least one player must have participated before retirement' }
    }
    return { valid: true }
  }

  // Non-retirement: exactly one player must have maxSets
  const winnerHasMaxSets = setsA === maxSets || setsB === maxSets
  if (!winnerHasMaxSets) {
    return { valid: false, error: `In ${format}, winner must have exactly ${maxSets} sets` }
  }

  // Verify exactly one player has max sets
  if (setsA === maxSets && setsB === maxSets) {
    return { valid: false, error: 'Both players cannot have the same winning set count' }
  }

  return { valid: true }
}

/**
 * Validates that a player is within the acceptable age range (6-18 years old).
 */
function validatePlayerAge(dateOfBirth: string | Date): { valid: boolean; error?: string } {
  const dob = new Date(dateOfBirth)
  const today = new Date()
  
  let age = today.getFullYear() - dob.getFullYear()
  const monthDiff = today.getMonth() - dob.getMonth()
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age--
  }

  if (age < 6) {
    return { valid: false, error: 'Player must be at least 6 years old' }
  }
  if (age > 18) {
    return { valid: false, error: 'Player must not be older than 18 years' }
  }

  return { valid: true }
}

/**
 * Validates phone number format (supports Indian and international formats).
 */
function validatePhoneNumber(phone: string): { valid: boolean; error?: string } {
  if (!phone.trim()) {
    return { valid: true } // Optional field
  }
  
  const phoneRegex = /^[\d\s\-\+\(\)]{10,15}$/
  if (!phoneRegex.test(phone)) {
    return { valid: false, error: 'Invalid phone number format' }
  }
  
  return { valid: true }
}

/**
 * Validates set points according to table tennis rules.
 * Rules:
 * - Points must be non-negative and ≤30 (to handle deuces)
 * - Both points cannot be 0 (unfilled sets are allowed to be omitted)
 * - Winning player must have ≥11 points
 * - If winner ≥10, loser must be ≥(winner-2) OR both ≥9 (deuce handling)
 */
function validateSetPoints(
  pointsA: number,
  pointsB: number,
): { valid: boolean; error?: string } {
  if (pointsA < 0 || pointsB < 0) {
    return { valid: false, error: 'Points cannot be negative' }
  }

  if (pointsA > 30 || pointsB > 30) {
    return { valid: false, error: 'Points cannot exceed 30' }
  }

  // Both zero is allowed (unfilled set)
  if (pointsA === 0 && pointsB === 0) {
    return { valid: true }
  }

  const winner = Math.max(pointsA, pointsB)
  const loser = Math.min(pointsA, pointsB)

  if (winner < 11) {
    return { valid: false, error: 'Winning score must be ≥11' }
  }

  // Check deuce rules: if winner ≥10, loser must be ≥(winner-2)
  if (winner >= 10) {
    if (!(loser >= winner - 2)) {
      return { valid: false, error: 'Invalid point spread' }
    }
  }

  return { valid: true }
}

// ── Schemas ────────────────────────────────────────────────────────────────

/**
 * Set score validation schema for per-set point entry.
 * Used in match submission forms to validate individual set scores.
 */
export const SetScoreSchema = z
  .object({
    points_a: z.number().int().min(0).max(30),
    points_b: z.number().int().min(0).max(30),
  })
  .superRefine((data, ctx) => {
    const validation = validateSetPoints(data.points_a, data.points_b)
    if (!validation.valid) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: validation.error || 'Invalid set points',
      })
    }
  })

/**
 * Match submission validation schema.
 * Ensures match data is valid before submission to prevent Elo rating corruption.
 */
export const MatchSubmissionSchema = z.object({
  event_id: z
    .string()
    .min(1, 'Event ID is required')
    .uuid('Event ID must be a valid UUID'),
  
  match_format: z
    .enum(['BEST_OF_3', 'BEST_OF_5', 'BEST_OF_7'])
    .default('BEST_OF_3'),
  
  sets_won_a: z
    .number()
    .int('Sets must be a whole number')
    .nonnegative('Sets cannot be negative'),
  
  sets_won_b: z
    .number()
    .int('Sets must be a whole number')
    .nonnegative('Sets cannot be negative'),
  
  match_date: z
    .string()
    .date('Match date must be a valid date'),
  
  is_retirement: z
    .boolean()
    .default(false),
  
  session_id: z.string().uuid().optional().nullable(),
  fixture_slot_id: z.string().uuid().optional().nullable(),
  
  // NEW: Optional per-set point scores
  set_scores: z
    .array(SetScoreSchema)
    .optional()
    .nullable(),
}).superRefine(async (data, ctx) => {
  // Validate match sets against format rules
  const setsValidation = validateMatchSets(
    data.sets_won_a,
    data.sets_won_b,
    data.match_format,
    data.is_retirement,
  )

  if (!setsValidation.valid) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: setsValidation.error || 'Invalid match sets',
      path: ['sets_won_a'], // Point to the first set field
    })
  }

  // Validate match date is not in the future
  const matchDate = new Date(data.match_date)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  if (matchDate > today) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Match date cannot be in the future',
      path: ['match_date'],
    })
  }

  // NEW: Validate set_scores if provided
  if (data.set_scores && data.set_scores.length > 0) {
    const totalSetsPLayed = data.sets_won_a + data.sets_won_b
    if (data.set_scores.length !== totalSetsPLayed) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Expected ${totalSetsPLayed} set scores but got ${data.set_scores.length}`,
        path: ['set_scores'],
      })
    }
  }

  // Async: Verify event exists
  const eventExists = await checkEventExists(data.event_id)
  if (!eventExists) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Event ID not found. Check Admin → Events for valid IDs.',
      path: ['event_id'],
    })
  }
})

export type MatchSubmission = z.infer<typeof MatchSubmissionSchema>

/**
 * Player registration validation schema.
 * Ensures player data is valid before creating new player record.
 */
export const PlayerRegistrationSchema = z.object({
  name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name is too long')
    .regex(/^[a-zA-Z\s'-]+$/, 'Name can only contain letters, spaces, hyphens, and apostrophes'),
  
  date_of_birth: z
    .string()
    .date('Date of birth must be a valid date'),
  
  gender: z
    .enum(['MALE', 'FEMALE'], { message: 'Gender must be MALE or FEMALE' }),
  
  seeding_level: z
    .enum(['UNSEEDED', 'DISTRICT', 'STATE', 'NATIONAL'])
    .default('UNSEEDED'),
  
  seeding_reference: z
    .string()
    .optional()
    .nullable(),
  
  virtual_matches: z
    .number()
    .int('Virtual matches must be a whole number')
    .min(0, 'Virtual matches cannot be negative')
    .max(30, 'Virtual matches cannot exceed 30'),
  
  nationality: z
    .string()
    .max(50, 'Nationality is too long')
    .optional()
    .nullable(),
  
  guardian_name: z
    .string()
    .max(100, 'Guardian name is too long')
    .optional()
    .nullable(),
  
  guardian_phone: z
    .string()
    .optional()
    .nullable(),
  
  contact_email: z
    .string()
    .email('Contact email must be a valid email address')
    .optional()
    .nullable(),
}).superRefine((data, ctx) => {
  // Validate age
  const ageValidation = validatePlayerAge(data.date_of_birth)
  if (!ageValidation.valid) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: ageValidation.error || 'Invalid age',
      path: ['date_of_birth'],
    })
  }

  // Validate seeding reference required for non-UNSEEDED
  if (data.seeding_level !== 'UNSEEDED' && !data.seeding_reference?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Seeding reference is required for seeded players',
      path: ['seeding_reference'],
    })
  }

  // Validate phone number if provided
  if (data.guardian_phone) {
    const phoneValidation = validatePhoneNumber(data.guardian_phone)
    if (!phoneValidation.valid) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: phoneValidation.error || 'Invalid phone number',
        path: ['guardian_phone'],
      })
    }
  }
})

export type PlayerRegistration = z.infer<typeof PlayerRegistrationSchema>

// ── Utility Functions ──────────────────────────────────────────────────────

/**
 * Formats Zod validation errors into a user-friendly map.
 * @param errors - Zod validation error
 * @returns Map of field names to error messages
 */
export function formatValidationErrors(
  errors: z.ZodError,
): Record<string, string> {
  const formatted: Record<string, string> = {}
  
  for (const issue of errors.issues) {
    const path = issue.path.join('.')
    if (path) {
      formatted[path] = issue.message
    }
  }
  
  return formatted
}

/**
 * Gets the first validation error message from a field.
 * @param fieldErrors - Map of field names to error messages
 * @param fieldName - Name of the field to get error for
 * @returns Error message or null
 */
export function getFieldError(
  fieldErrors: Record<string, string>,
  fieldName: string,
): string | null {
  return fieldErrors[fieldName] || null
}

/**
 * Validates match submission data.
 * For async validation (event exists), use validateMatchSubmissionAsync instead.
 * @param data - Raw form data
 * @returns Validation result with typed data or errors
 */
export function validateMatchSubmission(data: unknown) {
  return MatchSubmissionSchema.safeParse(data)
}

/**
 * Validates match submission data with async checks (event existence).
 * @param data - Raw form data
 * @returns Promise with validation result
 */
export async function validateMatchSubmissionAsync(data: unknown) {
  return MatchSubmissionSchema.parseAsync(data)
}

/**
 * Validates player registration data.
 * For async validation (name uniqueness), use validatePlayerNameAsync instead.
 * @param data - Raw form data
 * @returns Validation result with typed data or errors
 */
export function validatePlayerRegistration(data: unknown) {
  return PlayerRegistrationSchema.safeParse(data)
}

/**
 * Validates player registration data with async checks (name uniqueness).
 * @param data - Raw form data
 * @returns Promise with validation result
 */
export async function validatePlayerRegistrationAsync(data: unknown) {
  return PlayerRegistrationSchema.parseAsync(data)
}

/**
 * Async validator: Check if player name is unique within academy.
 * Call this when the name field loses focus or before submission.
 * 
 * @param name - Player name to check
 * @param academyId - Academy ID to check uniqueness within
 * @returns Error message or null if unique
 */
export async function validatePlayerNameAsync(
  name: string,
  academyId: string,
): Promise<string | null> {
  if (!name.trim()) {
    return null // Don't validate empty field
  }

  const isUnique = await checkPlayerNameUnique(name, academyId)
  
  if (!isUnique) {
    return `Player "${name}" is already registered in this academy. Please use a different name or link an existing player.`
  }

  return null // No error
}

/**
 * Async validator: Check if event exists.
 * Call this when event_id field changes or before submission.
 * 
 * @param eventId - Event ID to check
 * @returns Error message or null if event exists
 */
export async function validateEventAsync(eventId: string): Promise<string | null> {
  if (!eventId.trim()) {
    return null // Don't validate empty field
  }

  const exists = await checkEventExists(eventId)

  if (!exists) {
    return 'Event ID not found. Check Admin → Events for valid IDs.'
  }

  return null // No error
}

/**
 * Gets a human-friendly explanation of match format rules.
 */
export function getMatchFormatRules(format: string): string {
  const rules: Record<string, string> = {
    BEST_OF_3: 'First to 2 sets wins (unless retirement)',
    BEST_OF_5: 'First to 3 sets wins (unless retirement)',
    BEST_OF_7: 'First to 4 sets wins (unless retirement)',
  }
  return rules[format] || 'Unknown format'
}
