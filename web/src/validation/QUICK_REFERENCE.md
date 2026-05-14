# Validation System: Quick Reference Guide

## Add Validation to Any Form

### Step 1: Import the Schema and Hook

```typescript
import { useFormValidation } from '../validation/useFormValidation'
import { MatchSubmissionSchema } from '../validation/schemas'
// OR
import { PlayerRegistrationSchema } from '../validation/schemas'
```

### Step 2: Initialize the Hook

```typescript
function MyForm() {
  const [formData, setFormData] = useState({...})
  
  // Initialize validation with desired schema
  const validation = useFormValidation(MatchSubmissionSchema)
  
  // ...rest of component
}
```

### Step 3: Add Validation on Submit

```typescript
const handleSubmit = () => {
  // Validate form data
  const result = validation.validate(formData)
  
  if (!result.valid) {
    // Validation failed - errors are already in validation.errors
    return
  }
  
  // Validation passed - proceed with API call
  await api.submitData(result.data)
}
```

### Step 4: Display Errors

```typescript
// Show field-level error
{validation.getError('field_name') && (
  <p className="text-red-400 text-xs mt-1">
    {validation.getError('field_name')}
  </p>
)}

// Style field with error state
<input
  className={validation.getError('field_name') 
    ? 'border-2 border-red-500'
    : 'border border-gray-700'
  }
/>

// Show all errors in summary
{validation.hasErrors && (
  <div className="bg-red-900/20 border border-red-700 text-red-300 rounded p-3 text-sm">
    <p className="font-semibold">Errors found:</p>
    {Object.entries(validation.errors).map(([field, msg]) => (
      <p key={field} className="text-xs">• {msg}</p>
    ))}
  </div>
)}
```

### Step 5: Clear Errors on Input

```typescript
<input
  onChange={(e) => {
    setFormData(f => ({...f, field_name: e.target.value}))
    // Clear error when user starts typing
    validation.clearError('field_name')
  }}
/>
```

---

## Creating a New Schema

### Basic Schema Template

```typescript
import { z } from 'zod'

export const MyFormSchema = z.object({
  // Required text field
  name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name is too long'),
  
  // Email field
  email: z
    .string()
    .email('Invalid email format'),
  
  // Optional text field
  notes: z
    .string()
    .optional()
    .nullable(),
  
  // Number field
  age: z
    .number()
    .int('Age must be a whole number')
    .min(0, 'Age cannot be negative')
    .max(120, 'Invalid age'),
  
  // Enum field
  status: z
    .enum(['ACTIVE', 'INACTIVE', 'PENDING']),
  
  // Boolean field
  agreed: z
    .boolean()
    .default(false),
})

export type MyForm = z.infer<typeof MyFormSchema>
```

### Advanced: Cross-Field Validation

```typescript
export const MyFormSchema = z.object({
  password: z.string().min(8),
  confirm_password: z.string(),
  // ... other fields
}).superRefine((data, ctx) => {
  // Custom validation logic
  if (data.password !== data.confirm_password) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Passwords do not match',
      path: ['confirm_password'],
    })
  }
  
  // Another example: conditional validation
  if (data.status === 'ACTIVE' && !data.approved_by) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Must specify who approved activation',
      path: ['approved_by'],
    })
  }
})
```

---

## Common Validation Rules

### Text Fields

```typescript
// Simple required
name: z.string().min(1, 'Required')

// Min/max length
name: z.string()
  .min(2, 'At least 2 characters')
  .max(50, 'At most 50 characters')

// Pattern matching
username: z.string()
  .regex(/^[a-zA-Z0-9_]+$/, 'Only letters, numbers, underscores')

// Enumerated values
gender: z.enum(['MALE', 'FEMALE'])
```

### Numbers

```typescript
// Integer
age: z.number().int('Must be whole number')

// Range
rating: z.number()
  .min(1000, 'Rating too low')
  .max(2000, 'Rating too high')

// Non-negative
quantity: z.number().nonnegative('Cannot be negative')
```

### Dates

```typescript
// Simple date string
date: z.string().date('Invalid date format')

// With custom validation
birthDate: z.string().date().superRefine((value, ctx) => {
  const dob = new Date(value)
  const age = new Date().getFullYear() - dob.getFullYear()
  
  if (age < 18) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Must be 18+',
      path: [],
    })
  }
})
```

### Optional Fields

```typescript
// Optional, allows null
notes: z.string().optional().nullable()

// Optional, only string if provided
nickname: z.string().optional()

// Optional with default
status: z.string().default('PENDING')
```

---

## Validation Hook API Reference

### Properties

```typescript
const validation = useFormValidation(schema)

validation.errors      // Record<string, string> - All errors
                       // Example: { email: 'Invalid email', age: 'Too young' }

validation.hasErrors   // boolean - True if any errors exist
```

### Methods

```typescript
// Run validation on data
validation.validate(formData)
// Returns: { valid: boolean, errors?: Record<string, string>, data?: T }

// Get error message for specific field
validation.getError('field_name')
// Returns: string | null - Error message or null if no error

// Clear error for specific field
validation.clearError('field_name')

// Clear all errors
validation.clearAllErrors()
```

---

## Zod Cheat Sheet

```typescript
// String
z.string()
z.string().email()
z.string().url()
z.string().min(2).max(50)
z.string().regex(/pattern/)

// Number
z.number()
z.number().int()
z.number().positive()
z.number().min(0).max(100)

// Boolean
z.boolean()
z.boolean().default(false)

// Enum
z.enum(['A', 'B', 'C'])

// Date
z.date()
z.string().date() // "2025-01-01"

// Object
z.object({ field: z.string() })

// Array
z.array(z.string())
z.array(z.string()).min(1)

// Optional/Nullable
z.string().optional()      // Can be undefined
z.string().nullable()      // Can be null
z.string().optional().nullable() // Can be both

// Transformations
z.string().transform(val => val.toUpperCase())

// Conditionals
z.object({...}).superRefine((data, ctx) => {
  if (condition) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Error message',
      path: ['field_name'],
    })
  }
})
```

---

## Examples in Codebase

### Match Submission
📁 [web/src/pages/Dashboard.tsx](web/src/pages/Dashboard.tsx#L778-L900)
- Uses `MatchSubmissionSchema`
- Validates match format rules
- Real-time error display

### Player Registration
📁 [web/src/pages/Dashboard.tsx](web/src/pages/Dashboard.tsx#L1320-L1520)
- Uses `PlayerRegistrationSchema`
- Age validation with helpful text
- Seeding reference conditional validation

### Schema Definitions
📁 [web/src/validation/schemas.ts](web/src/validation/schemas.ts)
- All validation rules
- Custom validators (age, phone, match sets)
- Utility functions

---

## Common Patterns

### Pattern 1: Optional Conditional Field

```typescript
const [form, setForm] = useState({
  level: 'BEGINNER',
  certif_number: '',
})

const validation = useFormValidation(z.object({
  level: z.enum(['BEGINNER', 'ADVANCED']),
  certif_number: z.string().optional().nullable(),
}).superRefine((data, ctx) => {
  if (data.level === 'ADVANCED' && !data.certif_number) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Certificate required for Advanced level',
      path: ['certif_number'],
    })
  }
}))

// In render
{form.level === 'ADVANCED' && (
  <input
    value={form.certif_number}
    onChange={e => {
      setForm(f => ({...f, certif_number: e.target.value}))
      validation.clearError('certif_number')
    }}
    className={validation.getError('certif_number') 
      ? 'border-red-500' 
      : ''}
  />
)}
```

### Pattern 2: Range Validation with Context

```typescript
// Validate number of sets based on match format
z.object({
  format: z.enum(['BEST_OF_3', 'BEST_OF_5', 'BEST_OF_7']),
  sets_won: z.number(),
}).superRefine((data, ctx) => {
  const maxSets = {
    BEST_OF_3: 2,
    BEST_OF_5: 3,
    BEST_OF_7: 4,
  }
  
  const max = maxSets[data.format]
  
  if (data.sets_won > max) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `Maximum ${max} sets for ${data.format}`,
      path: ['sets_won'],
    })
  }
})
```

### Pattern 3: Email Already Registered (Async)

```typescript
// Future enhancement: async validation
async function validateEmailUnique(email: string) {
  const exists = await api.checkEmail(email)
  return !exists // True if valid (doesn't exist)
}

// Can be added to schema using .refine() for async checks
```

---

## Troubleshooting

### Issue: "Object is possibly null"
```typescript
// Wrong
const result = validation.validate(data)
console.log(result.data.field) // ❌ TypeScript error

// Right
const result = validation.validate(data)
if (result.valid) {
  console.log(result.data.field) // ✅ Type safe
}
```

### Issue: Fields have errors but validation says valid
```typescript
// Make sure all fields in the form are included in schema
const schema = z.object({
  name: z.string(),
  email: z.string().email(),
  // Add missing fields
  age: z.number(),
})
```

### Issue: Error message doesn't update
```typescript
// Make sure to call validation.validate() again after form changes
const result = validation.validate(newFormData)
// Don't rely on stale validation.errors
```

---

## Performance Tips

1. **Debounce if validating on every keystroke**
   ```typescript
   const debouncedValidate = useCallback(
     debounce((data) => validation.validate(data), 300),
     [validation]
   )
   ```

2. **Only validate on submit** (current approach)
   ```typescript
   const handleSubmit = () => {
     validation.validate(formData)
     // Validation runs once, errors stored
   }
   ```

3. **Validate specific fields only**
   ```typescript
   // Instead of full validation, validate single field
   const emailSchema = z.object({ email: z.string().email() })
   emailSchema.safeParse({ email: userInput })
   ```

---

## References

- **Zod Documentation**: https://zod.dev
- **Schema Definitions**: [web/src/validation/schemas.ts](web/src/validation/schemas.ts)
- **Complete Examples**: [web/src/validation/EXAMPLES.md](web/src/validation/EXAMPLES.md)
- **Full Documentation**: [web/src/validation/README.md](web/src/validation/README.md)
- **Implementation Guide**: [web/VALIDATION_IMPLEMENTATION.md](web/VALIDATION_IMPLEMENTATION.md)
