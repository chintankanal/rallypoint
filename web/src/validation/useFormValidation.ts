import { useState, useCallback, useRef } from 'react'
import { z } from 'zod'
import { formatValidationErrors, getFieldError } from './schemas'

/**
 * Custom hook for form validation.
 * Provides validation, error tracking, and field management.
 * Supports both sync and async validation.
 */
export function useFormValidation<T extends Record<string, unknown>>(schema: z.ZodSchema) {
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [asyncValidating, setAsyncValidating] = useState<Record<string, boolean>>({})
  const validateDebounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const validate = useCallback((data: unknown) => {
    const result = schema.safeParse(data)
    
    if (!result.success) {
      const formatted = formatValidationErrors(result.error)
      setErrors(formatted)
      return { valid: false, errors: formatted, data: null }
    }

    setErrors({})
    return { valid: true, errors: {}, data: result.data as T }
  }, [schema])

  /**
   * Async validation for individual fields or complete form.
   * Only works if schema has async validators (uses parseAsync).
   */
  const validateAsync = useCallback(async (data: unknown) => {
    try {
      const result = await (schema as any).parseAsync(data)
      setErrors({})
      return { valid: true, errors: {}, data: result as T }
    } catch (error) {
      if (error instanceof z.ZodError) {
        const formatted = formatValidationErrors(error)
        setErrors(formatted)
        return { valid: false, errors: formatted, data: null }
      }
      return { valid: false, errors: { _async: 'Validation error' }, data: null }
    }
  }, [schema])

  /**
   * Async validate a single field with debouncing.
   * Used for checking uniqueness, existence, etc.
   * 
   * @param fieldName - Field name to validate
   * @param validator - Async function that returns error message or null
   * @param debounceMs - Debounce delay in milliseconds (default: 500)
   */
  const validateFieldAsync = useCallback(
    async (
      fieldName: string,
      validator: () => Promise<string | null>,
      debounceMs = 500,
    ) => {
      // Clear existing timer
      if (validateDebounceTimers.current[fieldName]) {
        clearTimeout(validateDebounceTimers.current[fieldName])
      }

      // Set validating state
      setAsyncValidating(prev => ({ ...prev, [fieldName]: true }))

      // Debounce the validation
      const timer = setTimeout(async () => {
        try {
          const error = await validator()

          if (error) {
            setErrors(prev => ({ ...prev, [fieldName]: error }))
          } else {
            setErrors(prev => {
              const updated = { ...prev }
              delete updated[fieldName]
              return updated
            })
          }
        } catch (err) {
          // On error, clear validation state but don't block submission
          setErrors(prev => {
            const updated = { ...prev }
            delete updated[fieldName]
            return updated
          })
        } finally {
          setAsyncValidating(prev => ({ ...prev, [fieldName]: false }))
        }
      }, debounceMs)

      validateDebounceTimers.current[fieldName] = timer
    },
    [],
  )

  const clearError = useCallback((fieldName: string) => {
    setErrors(prev => {
      const updated = { ...prev }
      delete updated[fieldName]
      return updated
    })
  }, [])

  const clearAllErrors = useCallback(() => {
    setErrors({})
  }, [])

  const getError = useCallback((fieldName: string) => {
    return getFieldError(errors, fieldName)
  }, [errors])

  const isValidating = Object.values(asyncValidating).some(v => v)
  const hasErrors = Object.keys(errors).length > 0

  return {
    errors,
    validate,
    validateAsync,
    validateFieldAsync,
    clearError,
    clearAllErrors,
    getError,
    hasErrors,
    isValidating,
    isValidatingField: (fieldName: string) => asyncValidating[fieldName] ?? false,
  }
}

