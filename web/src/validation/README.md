# Form Validation & Safety Implementation

## Overview

This document describes the client-side form validation system implemented for the RallyPoint application. The system uses **Zod** for type-safe, runtime validation to prevent corrupt match data and invalid player registration from breaking the Elo rating algorithm and system integrity.

## Architecture

### Components

1. **`validation/schemas.ts`** - Zod validation schemas with custom business logic
2. **`validation/useFormValidation.ts`** - React hook for form validation state management
3. **`pages/Dashboard.tsx`** - Updated forms using the validation system

### Technology Stack

- **Zod** (v4.3.6) - Schema validation with TypeScript support
- **React** - Custom `useFormValidation` hook for state management
- **Tailwind CSS** - Visual feedback (red borders, error messages)

## Validation Rules

### Match Submission (`MatchSubmissionSchema`)

#### Field-Level Validation

| Field | Rule | Example |
|-------|------|---------|
| `event_id` | Required UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `match_format` | One of: `BEST_OF_3`, `BEST_OF_5`, `BEST_OF_7` | `BEST_OF_3` |
| `sets_won_a` | Integer, 0 to max sets | `2` |
| `sets_won_b` | Integer, 0 to max sets | `1` |
| `match_date` | Valid date, not in future | `2026-05-14` |
| `is_retirement` | Boolean | `false` |

#### Business Logic Validation

**Critical Rule**: Prevents corrupt match data that could break the Elo algorithm.

```
MATCH_FORMAT -> MAX_SETS_TO_WIN
BEST_OF_3    -> 2 sets
BEST_OF_5    -> 3 sets
BEST_OF_7    -> 4 sets
```

**Scenarios**:

1. **Normal Match** (is_retirement = false)
   - Exactly ONE player must have max sets for the format
   - Other player must have fewer sets
   - Examples:
     - BEST_OF_3: (2-0), (2-1) ✅ | (1-1) ❌ | (2-2) ❌
     - BEST_OF_5: (3-0), (3-1), (3-2) ✅ | (2-2) ❌

2. **Retirement/Walkover** (is_retirement = true)
   - At least one player must have participated (not 0-0)
   - Flexible set scores allowed
   - Examples: (1-0), (0-1), (1-1) ✅ | (0-0) ❌

### Player Registration (`PlayerRegistrationSchema`)

#### Field-Level Validation

| Field | Rule | Impact |
|-------|------|--------|
| `name` | 2-100 chars, letters/spaces/hyphens only | Player identity |
| `date_of_birth` | Valid date, age 6-18 years | Age eligibility |
| `gender` | MALE or FEMALE | Seeding, tier assignment |
| `seeding_level` | UNSEEDED, DISTRICT, STATE, or NATIONAL | Initial rating |
| `seeding_reference` | Required if not UNSEEDED | Verification |
| `virtual_matches` | 0-30, integer | Rating calculation |
| `nationality` | 0-50 chars | Optional |
| `guardian_phone` | Valid phone format | Parent contact |
| `contact_email` | Valid email | Notifications |

#### Age Validation

```
Age Calculation: today - date_of_birth
Acceptable: 6 ≤ age ≤ 18

Error Cases:
- age < 6: "Player must be at least 6 years old"
- age > 18: "Player must not be older than 18 years"
```

#### Seeding Rules

```
SEEDING_LEVEL -> INITIAL_RATING -> VIRTUAL_MATCHES -> SKIPS_PROVISIONAL
UNSEEDED      -> 1000           -> 0               -> NO (15 matches)
DISTRICT      -> 1200           -> 10              -> YES
STATE         -> 1400           -> 20              -> YES
NATIONAL      -> 1500           -> 30              -> YES
```

If `seeding_level !== UNSEEDED`, `seeding_reference` (certificate/ranking ID) is required.

## Usage

### In Components

```typescript
import { useFormValidation } from '../validation/useFormValidation'
import { MatchSubmissionSchema } from '../validation/schemas'

function MyForm() {
  const validation = useFormValidation(MatchSubmissionSchema)
  
  // Validate data
  const result = validation.validate(formData)
  
  if (!result.valid) {
    console.error(result.errors) // Record<string, string>
  }
  
  // Get single field error
  const nameError = validation.getError('name')
  
  // Clear error on field change
  validation.clearError('name')
  
  // Check if form has any errors
  if (validation.hasErrors) {
    // Don't submit
  }
}
```

### Error Handling

Errors are displayed as:

1. **Field-level errors** (red border + tooltip)
   ```
   Name: [input] (red border)
   "Name must be at least 2 characters"
   ```

2. **Summary errors** (alert box)
   ```
   Form validation errors:
   • Event ID must be a valid UUID
   • In BEST_OF_3, winner must have exactly 2 sets
   ```

3. **API errors** (separate from validation)
   ```
   "Player already registered in this academy"
   ```

## Technical Implementation

### Custom Hook: `useFormValidation`

```typescript
const validation = useFormValidation(schema)

// Properties
validation.errors       // Record<string, string> - All errors
validation.hasErrors    // boolean - True if any errors exist

// Methods
validation.validate(data)     // SafeParseReturnType - Full validation result
validation.getError(field)    // string | null - Single field error
validation.clearError(field)  // void - Clear field error
```

### Schema Composition

Schemas use:

- **Primitive validators** (`z.string()`, `z.number()`, etc.)
- **Custom validators** (`superRefine` for cross-field logic)
- **Type inference** (`z.infer<typeof Schema>`)

Example from `MatchSubmissionSchema`:

```typescript
const schema = z.object({
  sets_won_a: z.number().int().nonnegative(),
  sets_won_b: z.number().int().nonnegative(),
  match_format: z.enum(['BEST_OF_3', 'BEST_OF_5', 'BEST_OF_7']),
  is_retirement: z.boolean().default(false),
}).superRefine((data, ctx) => {
  // Cross-field validation: enforce match format rules
  const validation = validateMatchSets(
    data.sets_won_a,
    data.sets_won_b,
    data.match_format,
    data.is_retirement,
  )
  
  if (!validation.valid) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: validation.error,
      path: ['sets_won_a'],
    })
  }
})
```

## Validation Flow in SubmitMatchTab

```
1. User fills form
2. On field change: validation.clearError(fieldName)
3. User clicks submit
4. mutation.mutationFn:
   a. Check players selected
   b. Call validation.validate(formData)
   c. If invalid: throw error (displays in form)
   d. If valid: proceed to API call
5. On success: Clear form, reset validation
6. On API error: Show separate API error message
```

## Validation Flow in RegisterPlayerTab

```
1. User fills form
2. On field change: validation.clearError(fieldName)
3. User clicks register
4. mutation.mutationFn:
   a. Call validation.validate(formData)
   b. If invalid: throw error
   c. If valid: proceed to API call
5. On success: Clear form, show success message
6. On API error: Show separate API error message
```

## Testing Validation

### Match Submission Test Cases

```typescript
// Valid: BEST_OF_3, Player A wins
validate({ sets_won_a: 2, sets_won_b: 1, match_format: 'BEST_OF_3', is_retirement: false })
// ✅ Valid

// Invalid: BEST_OF_3, neither player has 2 sets
validate({ sets_won_a: 1, sets_won_b: 1, match_format: 'BEST_OF_3', is_retirement: false })
// ❌ "In BEST_OF_3, winner must have exactly 2 sets"

// Valid: Retirement with 1-0
validate({ sets_won_a: 1, sets_won_b: 0, match_format: 'BEST_OF_3', is_retirement: true })
// ✅ Valid

// Invalid: Retirement with 0-0
validate({ sets_won_a: 0, sets_won_b: 0, match_format: 'BEST_OF_3', is_retirement: true })
// ❌ "At least one player must have participated before retirement"

// Invalid: Sets exceed format maximum
validate({ sets_won_a: 3, sets_won_b: 1, match_format: 'BEST_OF_3', is_retirement: false })
// ❌ "Maximum 2 sets allowed in BEST_OF_3"
```

### Player Registration Test Cases

```typescript
// Valid: UNSEEDED player, age 10
validate({
  name: 'John Doe',
  date_of_birth: '2016-05-14',
  gender: 'MALE',
  seeding_level: 'UNSEEDED',
  virtual_matches: 0,
})
// ✅ Valid

// Invalid: Age too young
validate({
  name: 'Jane Doe',
  date_of_birth: '2021-05-14', // age 5
  // ...
})
// ❌ "Player must be at least 6 years old"

// Invalid: Seeded player without reference
validate({
  name: 'Arjun Sharma',
  // ... other fields
  seeding_level: 'STATE',
  seeding_reference: '', // Empty!
})
// ❌ "Seeding reference is required for seeded players"

// Invalid: Invalid phone format
validate({
  guardian_phone: 'abc123', // Not a phone
})
// ❌ "Invalid phone number format"
```

## Future Enhancements

1. **Server-side Validation Sync**
   - Mirror Zod schemas on backend (Python/Pydantic)
   - Ensure consistency across tiers

2. **Async Validators**
   - Check player registration uniqueness
   - Verify event exists before submission

3. **Conditional Field Validation**
   - Guardian info validation based on player age
   - Dynamic seeding reference formats

4. **Localization**
   - Multi-language error messages
   - Region-specific phone formats

5. **Analytics**
   - Track validation failure rates by field
   - Identify UX pain points

## Debugging

### Enable Validation Logging

Add to `useFormValidation.ts`:

```typescript
const validate = useCallback((data: unknown) => {
  const result = schema.safeParse(data)
  console.debug('Validation result:', {
    valid: result.success,
    data: result.success ? result.data : null,
    errors: !result.success ? result.error.issues : null,
  })
  // ...
}, [schema])
```

### Inspect Zod Schema

```typescript
console.log(MatchSubmissionSchema.shape)
// Shows all field definitions and validators
```

## References

- [Zod Documentation](https://zod.dev)
- [Zod Custom Validation](https://zod.dev/?id=superrefine)
- [Match Format Rules](../docs/jlrs_impl_plan.md)
- [Elo Rating Algorithm](../app/utils/rating_math.py)
