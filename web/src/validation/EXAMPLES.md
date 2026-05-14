# Form Validation Examples & Test Cases

## Quick Start: Using Validation in Your Component

```typescript
import { useFormValidation } from '../validation/useFormValidation'
import { MatchSubmissionSchema, PlayerRegistrationSchema } from '../validation/schemas'

function MyForm() {
  const validation = useFormValidation(MatchSubmissionSchema)
  const [formData, setFormData] = useState({...})

  const handleSubmit = () => {
    const result = validation.validate(formData)
    
    if (!result.valid) {
      // Show errors to user
      return
    }

    // Proceed with API call
    submitData(result.data)
  }

  return (
    <>
      {/* Render validation errors */}
      {validation.getError('sets_won_a') && (
        <p className="text-red-500">{validation.getError('sets_won_a')}</p>
      )}
      
      {/* Submit button disabled if errors exist */}
      <button disabled={validation.hasErrors || isLoading}>
        Submit
      </button>
    </>
  )
}
```

---

## Match Submission Validation Examples

### ✅ Valid Cases

#### Case 1: Normal Match - BEST_OF_3
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440000',
  match_format: 'BEST_OF_3',
  sets_won_a: 2,
  sets_won_b: 0,
  match_date: '2026-05-14',
  is_retirement: false,
}

validate(data)
// ✅ VALID
```

#### Case 2: BEST_OF_3 with competition
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440001',
  match_format: 'BEST_OF_3',
  sets_won_a: 2,
  sets_won_b: 1,
  match_date: '2026-05-13',
  is_retirement: false,
}

validate(data)
// ✅ VALID - Player A wins 2-1
```

#### Case 3: BEST_OF_5
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440002',
  match_format: 'BEST_OF_5',
  sets_won_a: 3,
  sets_won_b: 2,
  match_date: '2026-05-12',
  is_retirement: false,
}

validate(data)
// ✅ VALID - Player A wins 3-2
```

#### Case 4: Retirement with partial play
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440003',
  match_format: 'BEST_OF_3',
  sets_won_a: 1,
  sets_won_b: 0,
  match_date: '2026-05-11',
  is_retirement: true,
}

validate(data)
// ✅ VALID - Player B retired after losing 1 set
```

#### Case 5: BEST_OF_7 Early Dominance
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440004',
  match_format: 'BEST_OF_7',
  sets_won_a: 0,
  sets_won_b: 4,
  match_date: '2026-05-10',
  is_retirement: false,
}

validate(data)
// ✅ VALID - Player B wins 4-0 (first to 4 in BEST_OF_7)
```

### ❌ Invalid Cases

#### Case 1: Wrong Sets for Format
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440000',
  match_format: 'BEST_OF_3',
  sets_won_a: 1,      // ❌ Too low
  sets_won_b: 1,      // ❌ Too low
  match_date: '2026-05-14',
  is_retirement: false,
}

validate(data)
// ❌ ERROR: "In BEST_OF_3, winner must have exactly 2 sets"
// Explanation: In BEST_OF_3 (first to 2), one player MUST have 2 sets
```

#### Case 2: Both Players Have Max Sets
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440000',
  match_format: 'BEST_OF_3',
  sets_won_a: 2,      // ❌ Both have max
  sets_won_b: 2,      // ❌ Both have max
  match_date: '2026-05-14',
  is_retirement: false,
}

validate(data)
// ❌ ERROR: "Both players cannot have the same winning set count"
// Explanation: Impossible in match format - only one player wins
```

#### Case 3: Sets Exceed Format Maximum
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440000',
  match_format: 'BEST_OF_3',
  sets_won_a: 3,      // ❌ Exceeds max of 2
  sets_won_b: 1,
  match_date: '2026-05-14',
  is_retirement: false,
}

validate(data)
// ❌ ERROR: "Maximum 2 sets allowed in BEST_OF_3"
```

#### Case 4: Invalid UUID
```typescript
const data = {
  event_id: 'not-a-uuid',  // ❌ Not UUID format
  match_format: 'BEST_OF_3',
  sets_won_a: 2,
  sets_won_b: 1,
  match_date: '2026-05-14',
  is_retirement: false,
}

validate(data)
// ❌ ERROR: "Event ID must be a valid UUID"
```

#### Case 5: Retirement with No Participation
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440000',
  match_format: 'BEST_OF_3',
  sets_won_a: 0,      // ❌ Both 0
  sets_won_b: 0,      // ❌ Both 0
  match_date: '2026-05-14',
  is_retirement: true,
}

validate(data)
// ❌ ERROR: "At least one player must have participated before retirement"
// Explanation: A retirement needs context - someone must have played some sets
```

#### Case 6: Future Match Date
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440000',
  match_format: 'BEST_OF_3',
  sets_won_a: 2,
  sets_won_b: 1,
  match_date: '2026-12-31',  // ❌ In the future
  is_retirement: false,
}

validate(data)
// ❌ ERROR: "Match date cannot be in the future"
```

#### Case 7: Invalid Format
```typescript
const data = {
  event_id: '550e8400-e29b-41d4-a716-446655440000',
  match_format: 'BEST_OF_4',  // ❌ Not a valid option
  sets_won_a: 2,
  sets_won_b: 1,
  match_date: '2026-05-14',
  is_retirement: false,
}

validate(data)
// ❌ ERROR: "Invalid enum value"
```

---

## Player Registration Validation Examples

### ✅ Valid Cases

#### Case 1: Unseeded Player, Age 10
```typescript
const data = {
  name: 'Arjun Sharma',
  date_of_birth: '2016-05-14',  // Age: 10 ✅
  gender: 'MALE',
  seeding_level: 'UNSEEDED',
  seeding_reference: null,
  virtual_matches: 0,
  nationality: 'India',
  guardian_name: 'Rajesh Sharma',
  guardian_phone: '+91 9876543210',
  contact_email: 'rajesh@example.com',
}

validate(data)
// ✅ VALID
// Initial rating: 1000
// Provisional phase: 15 matches required
```

#### Case 2: Seeded District Player
```typescript
const data = {
  name: 'Priya Patel',
  date_of_birth: '2010-03-21',  // Age: 15 ✅
  gender: 'FEMALE',
  seeding_level: 'DISTRICT',
  seeding_reference: 'DIST-2024-001',  // Required for seeded
  virtual_matches: 10,  // Part of district seeding
  nationality: 'India',
  guardian_name: null,
  guardian_phone: null,
  contact_email: null,
}

validate(data)
// ✅ VALID
// Initial rating: 1200
// No provisional phase (skipped for seeded)
```

#### Case 3: National Level Player
```typescript
const data = {
  name: 'Vikram Singh',
  date_of_birth: '2008-07-10',  // Age: 17 ✅
  gender: 'MALE',
  seeding_level: 'NATIONAL',
  seeding_reference: 'NAT-2024-A123',
  virtual_matches: 30,  // Max virtual matches for national
  nationality: 'India',
  guardian_name: 'Harpreet Singh',
  guardian_phone: '+91-98765-43210',  // Flexible format
  contact_email: 'harpreet.singh@email.com',
}

validate(data)
// ✅ VALID
// Initial rating: 1500
// Experienced player, no provisional phase
```

#### Case 4: Minimal Valid Data
```typescript
const data = {
  name: 'Ali Khan',
  date_of_birth: '2015-11-30',  // Age: 10 ✅
  gender: 'MALE',
  seeding_level: 'UNSEEDED',
  seeding_reference: null,
  virtual_matches: 0,
  nationality: null,
  guardian_name: null,
  guardian_phone: null,
  contact_email: null,
}

validate(data)
// ✅ VALID - Optional fields can be null
```

### ❌ Invalid Cases

#### Case 1: Too Young
```typescript
const data = {
  name: 'Anjali Desai',
  date_of_birth: '2021-02-15',  // Age: 4 ❌ TOO YOUNG
  gender: 'FEMALE',
  seeding_level: 'UNSEEDED',
  // ...
}

validate(data)
// ❌ ERROR: "Player must be at least 6 years old"
```

#### Case 2: Too Old
```typescript
const data = {
  name: 'Rohit Kumar',
  date_of_birth: '2005-06-20',  // Age: 20 ❌ TOO OLD
  gender: 'MALE',
  seeding_level: 'UNSEEDED',
  // ...
}

validate(data)
// ❌ ERROR: "Player must not be older than 18 years"
```

#### Case 3: Seeded Without Reference
```typescript
const data = {
  name: 'Neha Gupta',
  date_of_birth: '2012-01-15',
  gender: 'FEMALE',
  seeding_level: 'STATE',  // Seeded level
  seeding_reference: '',   // ❌ REQUIRED for seeded
  // ...
}

validate(data)
// ❌ ERROR: "Seeding reference is required for seeded players"
```

#### Case 4: Invalid Name
```typescript
const data = {
  name: 'A',  // ❌ Too short
  date_of_birth: '2015-05-14',
  gender: 'MALE',
  // ...
}

validate(data)
// ❌ ERROR: "Name must be at least 2 characters"

// Also invalid:
// name: 'John123'  // ❌ Contains numbers
// name: 'José@'    // ❌ Contains special characters (@ not allowed)

// These ARE valid:
// name: 'Jean-Pierre'  // ✅ Hyphen allowed
// name: "O'Brien"      // ✅ Apostrophe allowed
// name: 'José'         // ✅ Accented characters OK (letters only)
```

#### Case 5: Invalid Gender
```typescript
const data = {
  name: 'Test Player',
  date_of_birth: '2015-05-14',
  gender: 'TRANS',  // ❌ Not in enum
  // ...
}

validate(data)
// ❌ ERROR: "Gender must be MALE or FEMALE"
```

#### Case 6: Invalid Virtual Matches
```typescript
const data = {
  name: 'Test Player',
  date_of_birth: '2015-05-14',
  gender: 'MALE',
  seeding_level: 'STATE',
  seeding_reference: 'STATE-001',
  virtual_matches: 35,  // ❌ Exceeds max of 30
  // ...
}

validate(data)
// ❌ ERROR: "Virtual matches cannot exceed 30"
```

#### Case 7: Invalid Email
```typescript
const data = {
  name: 'Test Player',
  date_of_birth: '2015-05-14',
  gender: 'MALE',
  contact_email: 'not-an-email',  // ❌ Invalid format
  // ...
}

validate(data)
// ❌ ERROR: "Contact email must be a valid email address"
```

#### Case 8: Invalid Phone
```typescript
const data = {
  name: 'Test Player',
  date_of_birth: '2015-05-14',
  gender: 'MALE',
  guardian_phone: 'abc',  // ❌ Invalid format
  // ...
}

validate(data)
// ❌ ERROR: "Invalid phone number format"
```

#### Case 9: Empty Name
```typescript
const data = {
  name: '',  // ❌ Empty
  date_of_birth: '2015-05-14',
  gender: 'MALE',
  // ...
}

validate(data)
// ❌ ERROR: "Name must be at least 2 characters"
```

---

## Error Display Pattern

### Match Submission Form
```
┌─────────────────────────────────────────┐
│ Form validation errors:                 │
│ • In BEST_OF_3, winner must have        │
│   exactly 2 sets                        │
│ • Match date cannot be in the future    │
└─────────────────────────────────────────┘

Sets Won (Player A)
[2____]  ← Field highlighted in red
"In BEST_OF_3, winner must have exactly 2 sets"

Match Date
[2026-12-31]  ← Field highlighted in red
"Match date cannot be in the future"
```

### Player Registration Form
```
┌─────────────────────────────────────────┐
│ Form validation errors:                 │
│ • Player must be at least 6 years old   │
│ • Seeding reference is required for     │
│   seeded players                        │
└─────────────────────────────────────────┘

Date of Birth
[2021-02-15]  ← Field highlighted in red
"Player must be at least 6 years old"

Seeding Reference
[________]  ← Field highlighted in red
"Seeding reference is required for seeded players"
```

---

## Testing Strategy

### Unit Test Example (Jest)
```typescript
import { MatchSubmissionSchema, PlayerRegistrationSchema } from '../validation/schemas'

describe('Match Submission Validation', () => {
  test('accepts valid BEST_OF_3 match', () => {
    const result = MatchSubmissionSchema.safeParse({
      event_id: '550e8400-e29b-41d4-a716-446655440000',
      match_format: 'BEST_OF_3',
      sets_won_a: 2,
      sets_won_b: 1,
      match_date: '2026-05-14',
      is_retirement: false,
    })
    
    expect(result.success).toBe(true)
  })

  test('rejects match with invalid set count', () => {
    const result = MatchSubmissionSchema.safeParse({
      event_id: '550e8400-e29b-41d4-a716-446655440000',
      match_format: 'BEST_OF_3',
      sets_won_a: 1,
      sets_won_b: 1,
      match_date: '2026-05-14',
      is_retirement: false,
    })
    
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toContain('winner must have')
    }
  })
})

describe('Player Registration Validation', () => {
  test('accepts valid unseeded player', () => {
    const result = PlayerRegistrationSchema.safeParse({
      name: 'Arjun Sharma',
      date_of_birth: '2016-05-14',
      gender: 'MALE',
      seeding_level: 'UNSEEDED',
      virtual_matches: 0,
    })
    
    expect(result.success).toBe(true)
  })

  test('rejects player who is too young', () => {
    const result = PlayerRegistrationSchema.safeParse({
      name: 'Test Child',
      date_of_birth: '2021-05-14',
      gender: 'MALE',
      seeding_level: 'UNSEEDED',
      virtual_matches: 0,
    })
    
    expect(result.success).toBe(false)
  })
})
```

---

## Debugging Validation

### Enable Console Logging
```typescript
// In useFormValidation.ts
const validate = useCallback((data: unknown) => {
  const result = schema.safeParse(data)
  
  console.debug('Validation Input:', data)
  console.debug('Validation Result:', result)
  
  // ... rest of validation
}, [schema])
```

### Inspect Validation Errors
```typescript
// In component
const result = validation.validate(formData)

if (!result.valid) {
  console.table(validation.errors)
  // Outputs:
  // ┌─────────────┬──────────────────────────────────────┐
  // │ (index)     │ Values                               │
  // ├─────────────┼──────────────────────────────────────┤
  // │ sets_won_a  │ "In BEST_OF_3, winner must have..." │
  // │ match_date  │ "Match date cannot be in the future" │
  // └─────────────┴──────────────────────────────────────┘
}
```

### View Zod Schema Structure
```typescript
import { MatchSubmissionSchema } from '../validation/schemas'

// Show all fields in schema
console.log(MatchSubmissionSchema.shape)

// Show specific field rules
console.log(MatchSubmissionSchema.shape.sets_won_a)
// ZodNumber { ... checks: [isInt, isNonNegative, ...] }
```
