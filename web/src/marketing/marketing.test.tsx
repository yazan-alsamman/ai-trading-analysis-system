import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRef } from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { membershipStore } from '@/app/membershipStore';
import { RegisterPage } from '@/features/auth/RegisterPage';
import { AssistantPanel } from '@/features/assistant/AssistantPanel';
import { EMPTY_CONTEXT } from '@/domain/assistant';
import { activeFrameListeners, useScrollProgress } from '@/motion/runtime';
import { renderWithProviders } from '@/test/render';
import { GENERAL_FAQ } from './content';
import { CompareTable, PlanGrid } from './membership/PlanComponents';
import { Faq } from './sections/Closing';
import { MembershipPage } from './pages/MembershipPage';

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  membershipStore.resetForTests();
});

describe('membership page', () => {
  it('selecting a plan records it and opens an honest confirmation (no checkout)', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MembershipPage />, { route: '/membership' });
    await user.click(screen.getAllByRole('radio', { name: 'Choose Professional' })[0]!);
    expect(membershipStore.getSelected()).toBe('professional');
    const sheet = screen.getByRole('dialog', { name: 'Your selection' });
    expect(within(sheet).getByText(/Paid activation is not available yet/)).toBeInTheDocument();
    expect(within(sheet).getByRole('link', { name: /Create account with Professional/ })).toHaveAttribute('href', '/register?plan=professional');
    expect(screen.queryByText(/\$\d/)).not.toBeInTheDocument(); // no invented prices anywhere
  });

  it('preselects a valid ?plan= and ignores an invalid one', () => {
    renderWithProviders(<MembershipPage />, { route: '/membership?plan=elite' });
    expect(membershipStore.getSelected()).toBe('elite');
    membershipStore.select(null);
    renderWithProviders(<MembershipPage />, { route: '/membership?plan=platinum' });
    expect(membershipStore.getSelected()).toBeNull();
  });
});

describe('plan components', () => {
  it('marks the selected plan with aria-checked', () => {
    render(<PlanGrid selected="essential" onSelect={() => undefined} />);
    expect(screen.getByRole('radio', { name: /Essential selected/ })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('radio', { name: 'Choose Elite' })).toHaveAttribute('aria-checked', 'false');
  });

  it('compares plans with explicit not-included and status labels', () => {
    render(<CompareTable highlight="professional" />);
    const table = screen.getByRole('table');
    expect(within(table).getByText('Your selection')).toBeInTheDocument();
    expect(within(table).getAllByText('Not included').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('Needs backend').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('Planned').length).toBeGreaterThan(0);
  });
});

describe('registration with a selected plan', () => {
  it('shows journey progress and the plan summary carried from the membership page', () => {
    renderWithProviders(<RegisterPage />, { route: '/register?plan=professional' });
    expect(screen.getByRole('navigation', { name: 'Sign-up progress' })).toBeInTheDocument();
    expect(screen.getByText('Selected plan')).toBeInTheDocument();
    expect(screen.getByText('Professional')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Change plan' })).toHaveAttribute('href', '/membership#plans');
    // Both the Sign in / Create account switch and the footer link keep the plan.
    for (const link of screen.getAllByRole('link', { name: 'Sign in' })) expect(link).toHaveAttribute('href', '/login?plan=professional');
  });

  it('validates the form before submitting', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />, { route: '/register' });
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('Enter your full name.')).toBeInTheDocument();
    expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument();
  });
});

describe('demo membership gating (UI preview only)', () => {
  it('is fully open without a demo plan, and shows upgrade information when the plan excludes a feature', () => {
    const props = { context: EMPTY_CONTEXT, shareRisk: false, onShareRisk: () => undefined, timeZone: 'UTC' };
    const { unmount } = renderWithProviders(<AssistantPanel {...props} />);
    expect(screen.getByRole('log', { name: 'Conversation' })).toBeInTheDocument();
    unmount();
    act(() => membershipStore.activateDemo('professional'));
    renderWithProviders(<AssistantPanel {...props} />);
    expect(screen.getByRole('region', { name: /AI assistant is not included/ })).toBeInTheDocument();
    expect(screen.getByText(/not real access control/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Preview Elite instead' })).toBeInTheDocument();
  });
});

describe('FAQ accordion', () => {
  it('opens one answer at a time and wires aria-expanded', async () => {
    const user = userEvent.setup();
    render(<Faq items={GENERAL_FAQ} />);
    const first = screen.getByRole('button', { name: GENERAL_FAQ[0]!.q });
    const second = screen.getByRole('button', { name: GENERAL_FAQ[1]!.q });
    expect(first).toHaveAttribute('aria-expanded', 'true');
    await user.click(second);
    expect(second).toHaveAttribute('aria-expanded', 'true');
    expect(first).toHaveAttribute('aria-expanded', 'false');
  });
});

describe('motion runtime', () => {
  function Probe({ enabled }: { enabled: boolean }) {
    const ref = useRef<HTMLDivElement>(null);
    useScrollProgress(ref, () => undefined, enabled);
    return <div ref={ref} style={{ height: 3000 }} />;
  }

  it('releases its scroll subscription on unmount (no leaked listeners)', () => {
    const before = activeFrameListeners();
    const { unmount } = render(<Probe enabled />);
    // jsdom has no IntersectionObserver → the runtime subscribes immediately.
    expect(activeFrameListeners()).toBe(before + 1);
    unmount();
    expect(activeFrameListeners()).toBe(before);
  });

  it('does not subscribe when disabled (reduced motion / compact screens)', () => {
    const before = activeFrameListeners();
    render(<Probe enabled={false} />);
    expect(activeFrameListeners()).toBe(before);
  });
});
