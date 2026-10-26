import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight } from 'lucide-react';
import { useId, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useLocation, useNavigate } from 'react-router';
import { useAuth, useServices } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Field, FormError, Input } from '@/components/ui/Form';
import { usePageTitle } from '@/hooks/usePageTitle';
import { safeRedirect } from '@/services/api/session';
import { userMessage } from '@/services/errors';
import { JourneySteps, PlanSummary } from '@/marketing/membership/Journey';
import { useJourneyPlan } from '@/marketing/membership/useJourneyPlan';
import { AuthCard } from './AuthCard';
import { PasswordInput } from './PasswordInput';
import { applyServerFieldErrors } from './serverErrors';
import { loginSchema, type LoginForm } from './schemas';

export function LoginPage() {
  usePageTitle('Sign in');
  const { login } = useAuth();
  const { source } = useServices();
  const navigate = useNavigate();
  const location = useLocation();
  // Only in-app paths are accepted as a destination after sign-in (no open redirects).
  const from = safeRedirect((location.state as { from?: unknown } | null)?.from);
  const [error, setError] = useState<string | null>(null);
  const [showRecovery, setShowRecovery] = useState(false);
  const plan = useJourneyPlan();
  const recoveryId = useId();
  const form = useForm<LoginForm>({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' }, mode: 'onTouched' });
  const { errors, isSubmitting } = form.formState;

  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await login(values);
      // With a plan chosen, continue the journey to the review step.
      navigate(plan ? `/welcome?plan=${plan}` : from, { replace: true, viewTransition: true });
    } catch (e) {
      applyServerFieldErrors(e, ['email', 'password'], form.setError);
      setError(userMessage(e));
    }
  });

  return (
    <AuthCard
      title="Welcome"
      muted="back."
      subtitle="Sign in to your workspaces, signals, risk profile and alerts."
      before={plan ? <JourneySteps current={1} /> : undefined}
      footer={
        <>
          New here?{' '}
          <Link to={plan ? `/register?plan=${plan}` : '/register'} viewTransition className="font-medium text-fg underline underline-offset-4 hover:text-accent">
            Create an account
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        {plan && <PlanSummary plan={plan} />}
        <FormError message={error} />
        <Field label="Email" error={errors.email?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} type="email" autoComplete="email" placeholder="name@example.com" className="h-11" aria-describedby={describedBy} invalid={invalid} {...form.register('email')} />
          )}
        </Field>
        <Field label="Password" error={errors.password?.message}>
          {({ id, describedBy, invalid }) => <PasswordInput id={id} autoComplete="current-password" aria-describedby={describedBy} invalid={invalid} {...form.register('password')} />}
        </Field>
        <div className="-mt-1 flex justify-end">
          <button
            type="button"
            aria-expanded={showRecovery}
            aria-controls={recoveryId}
            onClick={() => setShowRecovery((v) => !v)}
            className="text-xs font-medium text-fg-2 underline-offset-4 hover:text-fg hover:underline"
          >
            Forgot password?
          </button>
        </div>
        {showRecovery && (
          <p id={recoveryId} className="rounded-lg border border-line bg-inset px-3 py-2.5 text-xs text-fg-2">
            {source === 'demo'
              ? 'In demo mode there is no stored password — any password signs you in locally.'
              : 'Self-service recovery is not available yet: the backend has no password-reset endpoint. Ask the platform administrator to reset your account.'}
          </p>
        )}
        <Button type="submit" variant="primary" size="lg" shape="pill" loading={isSubmitting} trailingIcon={ArrowRight} className="mt-1 w-full">
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
