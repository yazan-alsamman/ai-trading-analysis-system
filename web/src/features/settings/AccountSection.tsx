import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useAuth, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Field, FormError, Input } from '@/components/ui/Form';
import { Panel } from '@/components/ui/Panel';
import { ROLE_LABELS } from '@/domain/user';
import { isApiError, userMessage } from '@/services/errors';
import { PasswordInput } from '../auth/PasswordInput';

const nameSchema = z.object({ name: z.string().trim().min(1, 'Enter your name.').max(200, 'Keep the name under 200 characters.') });

/** Mirrors the backend (backend/app/schemas/user.py): 8–128 characters, a letter and a digit. */
const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Enter your current password.'),
    newPassword: z
      .string()
      .min(8, 'Use at least 8 characters.')
      .max(128, 'Use at most 128 characters.')
      .regex(/[A-Za-z]/, 'Include at least one letter.')
      .regex(/\d/, 'Include at least one number.'),
    confirm: z.string(),
  })
  .refine((v) => v.newPassword === v.confirm, { path: ['confirm'], message: 'Passwords do not match.' })
  .refine((v) => v.newPassword !== v.currentPassword, { path: ['newPassword'], message: 'Choose a password different from the current one.' });

/**
 * Backend mode: the signed-in account (GET/PATCH /users/me, POST /users/me/password).
 * The role is assigned by the server and shown read-only.
 */
export function AccountSection() {
  const services = useServices();
  const { session, updateUser } = useAuth();
  const { notify } = useToast();
  const [nameError, setNameError] = useState<string | null>(null);
  const [pwError, setPwError] = useState<string | null>(null);

  const nameForm = useForm<z.infer<typeof nameSchema>>({ resolver: zodResolver(nameSchema), defaultValues: { name: session?.user.name ?? '' } });
  const pwForm = useForm<z.infer<typeof passwordSchema>>({ resolver: zodResolver(passwordSchema), defaultValues: { currentPassword: '', newPassword: '', confirm: '' } });

  if (!session || session.isDemo) return null;

  const saveName = nameForm.handleSubmit(async ({ name }) => {
    setNameError(null);
    try {
      updateUser(await services.account.updateProfile({ name }));
      nameForm.reset({ name });
      notify('Name saved.', 'success');
    } catch (e) {
      setNameError(userMessage(e));
    }
  });

  const changePassword = pwForm.handleSubmit(async ({ currentPassword, newPassword }) => {
    setPwError(null);
    try {
      await services.account.changePassword({ currentPassword, newPassword });
      pwForm.reset();
      notify('Password changed.', 'success');
    } catch (e) {
      // A wrong current password comes back as 400/422; keep what was typed (except passwords) so it can be corrected.
      if (isApiError(e) && e.kind === 'validation' && e.fieldErrors.new_password?.[0]) pwForm.setError('newPassword', { message: e.fieldErrors.new_password[0] });
      else setPwError(userMessage(e));
    }
  });

  return (
    <div id="account" className="scroll-mt-4">
      <Panel title="Account" meta={<Badge tone="info">{ROLE_LABELS[session.user.role]}</Badge>}>
        <div className="grid gap-8 lg:grid-cols-2">
          <form noValidate onSubmit={saveName} className="flex flex-col gap-4" aria-label="Profile">
            <p className="text-sm text-fg-2">
              Signed in as <span className="text-fg">{session.user.email}</span>. Your role is assigned by the server.
            </p>
            <Field label="Display name" error={nameForm.formState.errors.name?.message}>
              {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} autoComplete="name" invalid={invalid} {...nameForm.register('name')} />}
            </Field>
            <FormError message={nameError} />
            <Button type="submit" className="self-start" loading={nameForm.formState.isSubmitting} disabled={!nameForm.formState.isDirty}>
              Save name
            </Button>
          </form>

          <form noValidate onSubmit={changePassword} className="flex flex-col gap-4" aria-label="Change password">
            <Field label="Current password" error={pwForm.formState.errors.currentPassword?.message}>
              {({ id, describedBy, invalid }) => (
                <PasswordInput id={id} aria-describedby={describedBy} autoComplete="current-password" invalid={invalid} {...pwForm.register('currentPassword')} />
              )}
            </Field>
            <Field label="New password" error={pwForm.formState.errors.newPassword?.message} hint="8–128 characters, with a letter and a number.">
              {({ id, describedBy, invalid }) => (
                <PasswordInput id={id} aria-describedby={describedBy} autoComplete="new-password" invalid={invalid} {...pwForm.register('newPassword')} />
              )}
            </Field>
            <Field label="Confirm new password" error={pwForm.formState.errors.confirm?.message}>
              {({ id, describedBy, invalid }) => (
                <PasswordInput id={id} aria-describedby={describedBy} autoComplete="new-password" invalid={invalid} {...pwForm.register('confirm')} />
              )}
            </Field>
            <FormError message={pwError} />
            <Button type="submit" className="self-start" loading={pwForm.formState.isSubmitting}>
              Change password
            </Button>
          </form>
        </div>
      </Panel>
    </div>
  );
}
