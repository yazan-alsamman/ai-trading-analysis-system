import { describe, expect, it } from 'vitest';
import { priceAlertSchema } from './alerts/schemas';
import { loginSchema, registerSchema } from './auth/schemas';
import { postSchema } from './community/schemas';
import { channelSettingsSchema } from './settings/schemas';

const firstMessage = (r: { success: boolean; error?: { issues: { message: string }[] } }) => r.error?.issues[0]?.message;

describe('price alert validation', () => {
  const schema = priceAlertSchema((s) => (s === 'EURUSD' ? 1.08 : s === 'USDJPY' ? 150 : undefined));
  const base = { symbol: 'EURUSD' as const, condition: 'crosses_above' as const, price: 1.09, channels: ['app' as const], note: '' };

  it('accepts a valid alert', () => {
    expect(schema.safeParse(base).success).toBe(true);
  });

  it('requires a level on the correct side of the current price', () => {
    expect(firstMessage(schema.safeParse({ ...base, price: 1.07 }))).toMatch(/above the current price/);
    expect(firstMessage(schema.safeParse({ ...base, condition: 'crosses_below', price: 1.09 }))).toMatch(/below the current price/);
  });

  it('catches typos far from the market', () => {
    expect(firstMessage(schema.safeParse({ ...base, price: 10.8 }))).toMatch(/more than 30%/);
  });

  it('enforces instrument precision', () => {
    expect(firstMessage(schema.safeParse({ ...base, price: 1.090001 }))).toMatch(/5 decimal places/);
    expect(firstMessage(schema.safeParse({ ...base, symbol: 'USDJPY', price: 151.1234 }))).toMatch(/3 decimal places/);
  });

  it('requires at least one channel and a number', () => {
    expect(firstMessage(schema.safeParse({ ...base, channels: [] }))).toMatch(/at least one delivery channel/);
    expect(firstMessage(schema.safeParse({ ...base, price: Number.NaN }))).toMatch(/Enter a price level/);
  });
});

describe('auth validation', () => {
  it('validates email and password presence on login', () => {
    expect(loginSchema.safeParse({ email: 'a@b.co', password: 'x' }).success).toBe(true);
    expect(firstMessage(loginSchema.safeParse({ email: 'nope', password: 'x' }))).toMatch(/valid email/);
  });

  it('enforces password strength, matching confirmation and the advice acknowledgement', () => {
    const ok = { name: 'Elias', email: 'e@x.io', password: 'abcd1234', confirmPassword: 'abcd1234', acceptTerms: true };
    expect(registerSchema.safeParse(ok).success).toBe(true);
    expect(firstMessage(registerSchema.safeParse({ ...ok, password: 'abcdefgh', confirmPassword: 'abcdefgh' }))).toMatch(/number/);
    expect(firstMessage(registerSchema.safeParse({ ...ok, confirmPassword: 'other123' }))).toMatch(/do not match/);
    expect(firstMessage(registerSchema.safeParse({ ...ok, acceptTerms: false }))).toMatch(/financial advice/);
  });
});

describe('channel settings validation', () => {
  const off = { app: { enabled: true }, email: { enabled: false, address: '' }, telegram: { enabled: false, handle: '' } };
  it('only requires contact details for enabled channels', () => {
    expect(channelSettingsSchema.safeParse(off).success).toBe(true);
    expect(firstMessage(channelSettingsSchema.safeParse({ ...off, email: { enabled: true, address: 'bad' } }))).toMatch(/valid email/);
    expect(firstMessage(channelSettingsSchema.safeParse({ ...off, telegram: { enabled: true, handle: '@ab' } }))).toMatch(/Telegram username/);
    expect(channelSettingsSchema.safeParse({ ...off, telegram: { enabled: true, handle: '@trader_name' } }).success).toBe(true);
  });
});

describe('post validation', () => {
  it('bounds length and tags', () => {
    expect(postSchema.safeParse({ body: 'short', symbols: [] }).success).toBe(false);
    expect(postSchema.safeParse({ body: 'A long enough post body', symbols: ['EURUSD'] }).success).toBe(true);
    expect(postSchema.safeParse({ body: 'A long enough post body', symbols: ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD'] }).success).toBe(false);
  });
});

describe('password strength (round 3)', () => {
  it('mirrors the backend rules and never blocks on advice-only checks', async () => {
    const { passwordChecks, passwordStrength, registerSchema } = await import('./auth/schemas');
    expect(passwordStrength('')).toBe('empty');
    expect(passwordStrength('abcdefgh')).toBe('too-weak'); // no digit — the backend rejects it too
    expect(passwordStrength('abcdefg1')).toBe('acceptable');
    expect(passwordStrength('Abcdefghijk1')).toBe('strong');
    expect(passwordChecks('abc').filter((c) => c.required).map((c) => c.ok)).toEqual([false, true, false]);
    const base = { name: 'Sara K', email: 'sara@example.com', confirmPassword: '', acceptTerms: true };
    expect(registerSchema.safeParse({ ...base, password: 'abcdefg1', confirmPassword: 'abcdefg1' }).success).toBe(true);
    expect(registerSchema.safeParse({ ...base, password: 'a1'.repeat(65), confirmPassword: 'a1'.repeat(65) }).success).toBe(false);
  });
});
