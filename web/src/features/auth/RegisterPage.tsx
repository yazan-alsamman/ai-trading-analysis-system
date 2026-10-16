import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight } from 'lucide-react';
import { useId, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router';
import { useAuth } from '@/app/contexts';
import { Button } from '@/components/ui/Button';
import { Checkbox, Field, FormError, Input } from '@/components/ui/Form';
import { usePageTitle } from '@/hooks/usePageTitle';
import { userMessage } from '@/services/errors';
import { JourneySteps, PlanSummary } from '@/marketing/membership/Journey';
import { useJourneyPlan } from '@/marketing/membership/useJourneyPlan';
import { AuthCard } from './AuthCard';
import { PasswordInput, PasswordStrength } from './PasswordInput';
import { applyServerFieldErrors } from './serverErrors';
import { registerSchema, type RegisterForm } from './schemas';

export function RegisterPage() {
  usePageTitle('Create account');
  const { register: registerAccount } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const strengthId = useId();
  const plan = useJourneyPlan();
  const form = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: '', email: '', password: '', confirmPassword: '', acceptTerms: false },
    mode: 'onTouched',
  });
  const { errors, isSubmitting } = form.formState;
  const password = form.watch('password');

  const submit = form.handleSubmit(async ({ name, email, password: pw }) => {
    setError(null);
    try {
      await registerAccount({ name, email, password: pw });
      navigate(plan ? `/welcome?plan=${plan}` : '/welcome', { replace: true, viewTransition: true });
    } catch (e) {
      applyServerFieldErrors(e, ['name', 'email', 'password'], form.setError);
      setError(userMessage(e));
    }
  });

  return (
    <AuthCard
      title="Open your"
      muted="research desk."
      subtitle="New accounts start as Trader. Analyst, expert and admin roles are assigned by the platform administrator."
      before={<JourneySteps current={1} />}
      footer={
        <>
          Already registered?{' '}
          <Link to={plan ? `/login?plan=${plan}` : '/login'} viewTransition className="font-medium text-fg underline underline-offset-4 hover:text-accent">
            Sign in
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        {plan ? (
          <PlanSummary plan={plan} />
        ) : (
          <p className="text-sm text-fg-2">
            No plan selected —{' '}
            <Link to="/membership#plans" viewTransition className="font-medium text-fg underline underline-offset-4">
              compare plans
            </Link>{' '}
            or continue and choose later.
          </p>
        )}
        <FormError message={error} />
        <Field label="Full name" error={errors.name?.message}>
          {({ id, describedBy, invalid }) => <Input id={id} autoComplete="name" className="h-11" aria-describedby={describedBy} invalid={invalid} {...form.register('name')} />}
        </Field>
        <Field label="Email" error={errors.email?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} type="email" autoComplete="email" placeholder="name@example.com" className="h-11" aria-describedby={describedBy} invalid={invalid} {...form.register('email')} />
          )}
        </Field>
        <Field label="Password" error={errors.password?.message}>
          {({ id, describedBy, invalid }) => (
            <PasswordInput id={id} autoComplete="new-password" aria-describedby={[describedBy, strengthId].filter(Boolean).join(' ')} invalid={invalid} {...form.register('password')} />
          )}
        </Field>
        <PasswordStrength value={password} id={strengthId} />
        <Field label="Confirm password" error={errors.confirmPassword?.message}>
          {({ id, describedBy, invalid }) => <PasswordInput id={id} autoComplete="new-password" aria-describedby={describedBy} invalid={invalid} {...form.register('confirmPassword')} />}
        </Field>
        <div>
          <Checkbox label="I understand this platform provides analysis only, not financial advice, and never executes trades." {...form.register('acceptTerms')} />
          {errors.acceptTerms?.message && <p className="mt-1.5 text-xs text-danger">{errors.acceptTerms.message}</p>}
        </div>
        <Button type="submit" variant="primary" size="lg" shape="pill" loading={isSubmitting} trailingIcon={ArrowRight} className="mt-1 w-full">
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
