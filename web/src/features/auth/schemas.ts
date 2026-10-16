import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().trim().min(1, 'Enter your email address.').pipe(z.email('Enter a valid email address, e.g. name@example.com.')),
  password: z.string().min(1, 'Enter your password.'),
});

export const registerSchema = z
  .object({
    name: z.string().trim().min(2, 'Enter your full name.').max(60, 'Keep the name under 60 characters.'),
    email: z.string().trim().min(1, 'Enter your email address.').pipe(z.email('Enter a valid email address, e.g. name@example.com.')),
    password: z
      .string()
      .min(8, 'Use at least 8 characters.')
      .max(128, 'Use at most 128 characters.')
      .regex(/[A-Za-z]/, 'Include at least one letter.')
      .regex(/\d/, 'Include at least one number.'),
    confirmPassword: z.string(),
    acceptTerms: z.boolean().refine((v) => v, 'Please confirm you understand the platform does not provide financial advice.'),
  })
  .refine((v) => v.password === v.confirmPassword, { path: ['confirmPassword'], message: 'Passwords do not match.' });

export type LoginForm = z.infer<typeof loginSchema>;
export type RegisterForm = z.infer<typeof registerSchema>;

/**
 * Password rules shown while typing. The `required` ones mirror the backend
 * exactly (backend/app/schemas/user.py: 8–128 chars, a letter and a digit);
 * the others are advice and never block registration.
 */
export interface PasswordCheck {
  label: string;
  ok: boolean;
  required: boolean;
}

export function passwordChecks(pw: string): PasswordCheck[] {
  return [
    { label: '8+ characters', ok: pw.length >= 8, required: true },
    { label: 'A letter', ok: /[A-Za-z]/.test(pw), required: true },
    { label: 'A number', ok: /\d/.test(pw), required: true },
    { label: '12+ characters', ok: pw.length >= 12, required: false },
    { label: 'Symbol or mixed case', ok: /[^A-Za-z0-9]/.test(pw) || (/[a-z]/.test(pw) && /[A-Z]/.test(pw)), required: false },
  ];
}

export type PasswordStrength = 'empty' | 'too-weak' | 'acceptable' | 'strong';

export function passwordStrength(pw: string): PasswordStrength {
  if (!pw) return 'empty';
  const checks = passwordChecks(pw);
  if (checks.some((c) => c.required && !c.ok)) return 'too-weak';
  return checks.every((c) => c.ok) ? 'strong' : 'acceptable';
}
