import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useLocation, useNavigate } from 'react-router';
import { useAuth } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Field, FormError, Input } from '@/components/ui/Form';
import { usePageTitle } from '@/hooks/usePageTitle';
import { userMessage } from '@/services/errors';
import { AuthCard } from './AuthCard';
import { applyServerFieldErrors } from './serverErrors';
import { loginSchema, type LoginForm } from './schemas';

export function LoginPage() {
  usePageTitle('Sign in');
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/workspace';
  const [error, setError] = useState<string | null>(null);
  const form = useForm<LoginForm>({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' }, mode: 'onTouched' });
  const { errors, isSubmitting } = form.formState;

  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await login(values);
      navigate(from, { replace: true });
    } catch (e) {
      applyServerFieldErrors(e, ['email', 'password'], form.setError);
      setError(userMessage(e));
    }
  });

  return (
    <AuthCard
      title="Sign in"
      subtitle="Access your workspaces, alerts and AI analysis."
      footer={
        <>
          No account?{' '}
          <Link to="/register" className="font-medium text-accent underline-offset-2 hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        <FormError message={error} />
        <Field label="Email" error={errors.email?.message}>
          {({ id, describedBy, invalid }) => <Input id={id} type="email" autoComplete="email" aria-describedby={describedBy} invalid={invalid} {...form.register('email')} />}
        </Field>
        <Field label="Password" error={errors.password?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} type="password" autoComplete="current-password" aria-describedby={describedBy} invalid={invalid} {...form.register('password')} />
          )}
        </Field>
        <Button type="submit" variant="primary" loading={isSubmitting} className="mt-1 w-full">
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
