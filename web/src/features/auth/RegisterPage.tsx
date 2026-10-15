import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router';
import { useAuth } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Checkbox, Field, FormError, Input } from '@/components/ui/Form';
import { usePageTitle } from '@/hooks/usePageTitle';
import { userMessage } from '@/services/errors';
import { AuthCard } from './AuthCard';
import { applyServerFieldErrors } from './serverErrors';
import { registerSchema, type RegisterForm } from './schemas';

export function RegisterPage() {
  usePageTitle('Create account');
  const { register: registerAccount } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: '', email: '', password: '', confirmPassword: '', acceptTerms: false },
    mode: 'onTouched',
  });
  const { errors, isSubmitting } = form.formState;

  const submit = form.handleSubmit(async ({ name, email, password }) => {
    setError(null);
    try {
      await registerAccount({ name, email, password });
      navigate('/workspace', { replace: true });
    } catch (e) {
      applyServerFieldErrors(e, ['name', 'email', 'password'], form.setError);
      setError(userMessage(e));
    }
  });

  return (
    <AuthCard
      title="Create account"
      subtitle="Your role (trader, analyst, expert) is assigned by the platform administrator."
      footer={
        <>
          Already registered?{' '}
          <Link to="/login" className="font-medium text-accent underline-offset-2 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        <FormError message={error} />
        <Field label="Full name" error={errors.name?.message}>
          {({ id, describedBy, invalid }) => <Input id={id} autoComplete="name" aria-describedby={describedBy} invalid={invalid} {...form.register('name')} />}
        </Field>
        <Field label="Email" error={errors.email?.message}>
          {({ id, describedBy, invalid }) => <Input id={id} type="email" autoComplete="email" aria-describedby={describedBy} invalid={invalid} {...form.register('email')} />}
        </Field>
        <Field label="Password" hint="At least 8 characters, including a letter and a number." error={errors.password?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} type="password" autoComplete="new-password" aria-describedby={describedBy} invalid={invalid} {...form.register('password')} />
          )}
        </Field>
        <Field label="Confirm password" error={errors.confirmPassword?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} type="password" autoComplete="new-password" aria-describedby={describedBy} invalid={invalid} {...form.register('confirmPassword')} />
          )}
        </Field>
        <div>
          <Checkbox label="I understand this platform provides analysis only, not financial advice, and never executes trades." {...form.register('acceptTerms')} />
          {errors.acceptTerms?.message && <p className="mt-1.5 text-xs text-danger">{errors.acceptTerms.message}</p>}
        </div>
        <Button type="submit" variant="primary" loading={isSubmitting} className="mt-1 w-full">
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
