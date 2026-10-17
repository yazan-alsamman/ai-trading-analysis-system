import type { FieldValues, Path, UseFormSetError } from 'react-hook-form';
import { isApiError } from '@/services/errors';

/** Map Laravel-style field errors from the server onto form fields. */
export function applyServerFieldErrors<T extends FieldValues>(error: unknown, fields: readonly Path<T>[], setError: UseFormSetError<T>): void {
  if (!isApiError(error)) return;
  for (const field of fields) {
    const message = error.fieldErrors[field]?.[0];
    if (message) setError(field, { message });
  }
}
