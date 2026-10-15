/**
 * One error type for every data operation, so UI code handles failures the
 * same way whether data came from the demo layer or the backend.
 */
export type ApiErrorKind =
  | 'network' // request never reached the server
  | 'timeout'
  | 'aborted' // cancelled by the client (e.g. user switched instrument)
  | 'unauthorized' // 401 — session missing or expired
  | 'forbidden' // 403 — role not permitted
  | 'not_found'
  | 'validation' // 422 — input rejected by the server
  | 'rate_limited' // 429
  | 'server' // 5xx
  | 'contract' // response did not match the expected schema
  | 'not_available'; // feature needs a backend service that is not connected

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | undefined;
  /** Field-level messages (Laravel-style `errors: { field: [msg] }`). */
  readonly fieldErrors: Record<string, string[]>;

  constructor(kind: ApiErrorKind, message: string, options: { status?: number; fieldErrors?: Record<string, string[]>; cause?: unknown } = {}) {
    super(message, { cause: options.cause });
    this.name = 'ApiError';
    this.kind = kind;
    this.status = options.status;
    this.fieldErrors = options.fieldErrors ?? {};
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isAbort(error: unknown): boolean {
  return (
    (isApiError(error) && error.kind === 'aborted') ||
    (error instanceof DOMException && error.name === 'AbortError')
  );
}

/** Plain-language message for display. Never exposes stack traces or raw bodies. */
export function userMessage(error: unknown): string {
  if (!isApiError(error)) return 'Something went wrong. Please try again.';
  switch (error.kind) {
    case 'network':
      return 'Could not reach the server. Check your connection and try again.';
    case 'timeout':
      return 'The server took too long to respond. Please try again.';
    case 'aborted':
      return 'The request was cancelled.';
    case 'unauthorized':
      return 'Your session has expired. Please sign in again.';
    case 'forbidden':
      return 'Your account does not have access to this.';
    case 'not_found':
      return 'The requested item could not be found.';
    case 'validation':
      return error.message || 'Some fields need attention.';
    case 'rate_limited':
      return 'Too many requests. Please wait a moment and try again.';
    case 'server':
      return 'The server encountered an error. Please try again shortly.';
    case 'contract':
      return 'The server returned data in an unexpected format. The issue has been logged.';
    case 'not_available':
      return error.message || 'This feature needs a backend service that is not connected yet.';
  }
}
