import { useSyncExternalStore } from 'react';
import { z } from 'zod';
import { PLAN_IDS, type PlanId } from '@/domain/membership';

/**
 * Frontend-only membership state. NOT authorisation and NOT a subscription:
 *  - `selected`: the package a visitor picked before creating an account
 *    (sessionStorage — it only needs to survive the sign-up journey).
 *  - `demo`: a labelled DEMO membership used to preview plan-aware UI
 *    (localStorage). Nothing is purchased, verified or enforced.
 */

const SELECTED_KEY = 'ata.membership.selected.v1';
const DEMO_KEY = 'ata.membership.demo.v1';

const SelectedSchema = z.object({ plan: z.enum(PLAN_IDS), at: z.number() });
const DemoSchema = z.object({ plan: z.enum(PLAN_IDS), activatedAt: z.number(), demo: z.literal(true) });

export type DemoMembership = z.infer<typeof DemoSchema>;

function read<T>(storage: () => Storage, key: string, schema: z.ZodType<T>): T | null {
  try {
    const raw = storage().getItem(key);
    if (!raw) return null;
    const parsed = schema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

function write(storage: () => Storage, key: string, value: unknown): void {
  try {
    if (value === null) storage().removeItem(key);
    else storage().setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — state lives for this page view only */
  }
}

const session = () => window.sessionStorage;
const local = () => window.localStorage;

let selected: PlanId | null | undefined;
let demo: DemoMembership | null | undefined;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const membershipStore = {
  getSelected(): PlanId | null {
    if (selected === undefined) selected = read(session, SELECTED_KEY, SelectedSchema)?.plan ?? null;
    return selected;
  },
  select(plan: PlanId | null): void {
    selected = plan;
    write(session, SELECTED_KEY, plan ? { plan, at: Date.now() } : null);
    emit();
  },
  getDemo(): DemoMembership | null {
    if (demo === undefined) demo = read(local, DEMO_KEY, DemoSchema);
    return demo;
  },
  activateDemo(plan: PlanId): void {
    demo = { plan, activatedAt: Date.now(), demo: true };
    write(local, DEMO_KEY, demo);
    emit();
  },
  clearDemo(): void {
    demo = null;
    write(local, DEMO_KEY, null);
    emit();
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  /** Tests only: forget cached values so storage is re-read. */
  resetForTests(): void {
    selected = undefined;
    demo = undefined;
  },
};

export function useSelectedPlan(): PlanId | null {
  return useSyncExternalStore(membershipStore.subscribe, membershipStore.getSelected, () => null);
}

export function useDemoMembership(): DemoMembership | null {
  return useSyncExternalStore(membershipStore.subscribe, membershipStore.getDemo, () => null);
}
