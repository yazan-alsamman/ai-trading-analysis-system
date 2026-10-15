import { z } from 'zod';

/** Notification channel settings (SF7). Contact details are required only for enabled channels. */
export const channelSettingsSchema = z
  .object({
    app: z.object({ enabled: z.boolean() }),
    email: z.object({ enabled: z.boolean(), address: z.string().trim() }),
    telegram: z.object({ enabled: z.boolean(), handle: z.string().trim() }),
  })
  .superRefine((v, ctx) => {
    if (v.email.enabled && !z.email().safeParse(v.email.address).success) {
      ctx.addIssue({ code: 'custom', path: ['email', 'address'], message: 'Enter a valid email address, e.g. name@example.com.' });
    }
    if (v.telegram.enabled && !/^@?[A-Za-z][A-Za-z0-9_]{4,31}$/.test(v.telegram.handle)) {
      ctx.addIssue({ code: 'custom', path: ['telegram', 'handle'], message: 'Enter a Telegram username: 5–32 letters, digits or underscores, e.g. @trader_name.' });
    }
  });

export type ChannelSettingsForm = z.infer<typeof channelSettingsSchema>;

export const workspaceNameSchema = z
  .string()
  .trim()
  .min(1, 'Give the workspace a name.')
  .max(40, 'Keep the name under 40 characters.');
