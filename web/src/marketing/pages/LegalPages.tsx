import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';

function LegalPage({ eyebrow, title, intro, updated, children }: { eyebrow: string; title: string; intro: string; updated: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-5 pt-32 pb-24 sm:px-8">
      <p className="eyebrow mb-3">{eyebrow}</p>
      <h1 className="display text-d2 text-fg">{title}</h1>
      <p className="mt-4 text-md text-fg-2">{intro}</p>
      <p className="mt-2 text-xs text-fg-3">Last updated {updated}</p>
      <div className="legal-body mt-10 flex flex-col gap-8 text-sm leading-6 text-fg-2">{children}</div>
    </article>
  );
}

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-lg font-semibold text-fg">{title}</h2>
      <div className="flex flex-col gap-2">{children}</div>
    </section>
  );
}

export function RiskDisclosurePage() {
  useDocumentMeta({
    title: 'Risk disclosure',
    description: 'What the platform is and is not, the risks of trading gold and FX, and how to read model outputs, simulated data and risk calculations.',
    path: '/legal/risk-disclosure',
  });
  return (
    <LegalPage
      eyebrow="Legal"
      title="Risk disclosure"
      updated="17 October 2026"
      intro="Please read this before using any analysis on this website or in the application. It explains what the platform does, what it does not do, and the limits of everything it shows."
    >
      <Part title="1. What the platform is">
        <p>
          AI Trading Assistance is a research and decision-support tool for gold (XAU/USD) and major foreign-exchange pairs. It shows charts, a model’s assessment with
          its supporting evidence, and position-sizing calculations based on figures you enter.
        </p>
        <p>
          It is <strong className="text-fg">not financial advice</strong>, it is <strong className="text-fg">not a broker</strong>, and it{' '}
          <strong className="text-fg">never places, modifies or closes trades</strong>. Any trading decision, and its consequences, are yours.
        </p>
      </Part>
      <Part title="2. Trading risk">
        <p>
          Trading gold and foreign exchange carries a high level of risk and may not be suitable for everyone. Leveraged products can lose value quickly, and you can lose
          more than you expect. Do not trade money you cannot afford to lose.
        </p>
        <p>
          A stop-loss is an instruction, not a guarantee: prices can gap past it, and slippage can make a loss larger than planned. An entry zone is an area of interest,
          not a guaranteed fill price.
        </p>
      </Part>
      <Part title="3. Model outputs are estimates">
        <p>
          The model’s probability is its estimate that the take-profit is reached before the stop-loss within a stated number of candles. It is an estimate that can be
          wrong — not a prediction that something will happen. A projected path is drawn only where the model supplied points, and only to the right of the NOW boundary;
          it is not a forecast of certainty.
        </p>
        <p>Contributing factors explain why the model produced its output. They do not prove that the market will follow.</p>
      </Part>
      <Part title="4. Simulated data and the absence of verified results">
        <p>
          In demo mode, and throughout this public website, market data and model outputs are <strong className="text-fg">simulated</strong> in your browser and labelled
          “Simulated”. They are examples of the workflow, not market information.
        </p>
        <p>
          No verified live track record exists yet. Performance figures shown on the site are computed from simulated predictions to demonstrate the evaluation method
          (hit rate, Brier score, calibration) and say nothing about the accuracy of the real model. Past or simulated results do not guarantee future results.
        </p>
      </Part>
      <Part title="5. Risk calculations depend on your inputs">
        <p>
          Position size, money at risk and limit checks are calculated from the capital, risk percentage, entry and stop you provide. The calculator assumes the stop
          fills at its price. It never guesses broker details: lots are shown only with the contract size you enter, cross-currency sizing needs a rate you enter, and
          margin is not calculated because it depends on your broker’s leverage.
        </p>
      </Part>
      <Part title="6. The assistant">
        <p>
          The assistant currently available is a <strong className="text-fg">rule-based demo</strong>, not a language model. It assembles answers with fixed rules from
          the data shown on screen. It cannot read news, see live prices beyond what is on screen, or predict prices.
        </p>
      </Part>
      <Part title="7. About this document">
        <p>
          This disclosure is informational. It has been written for a graduation project and has not been reviewed as a legal document; it is not a substitute for advice
          from a licensed professional. Terms of service and a privacy policy are in preparation. See also{' '}
          <Link to="/legal/data-storage" className="text-fg underline underline-offset-2">
            what this site stores in your browser
          </Link>
          .
        </p>
      </Part>
    </LegalPage>
  );
}

const STORED: { key: string; where: 'Local storage' | 'Session storage'; what: string }[] = [
  { key: 'ata.preferences.v1', where: 'Local storage', what: 'Your settings: theme, density, time zone, workspaces, alert channels, and the risk and signal profiles you enter.' },
  { key: 'ata.session.v1', where: 'Local storage', what: 'Your signed-in session (only after you sign in). Removed when you sign out.' },
  { key: 'ata.assistant.thread.v1', where: 'Local storage', what: 'Your conversation with the in-app assistant. “Clear conversation” deletes it.' },
  { key: 'ata.assistant.public.v1', where: 'Local storage', what: 'Your conversation with the assistant on this public website. “Clear conversation” deletes it.' },
  { key: 'ata.assistant.shareRisk.v1', where: 'Local storage', what: 'Whether you allow the in-app assistant to use your risk profile.' },
  { key: 'ata.notifications.v1', where: 'Local storage', what: 'In-app notifications shown in the application.' },
  { key: 'ata.demo.alerts.v1 · ata.demo.opportunityAlerts.v1', where: 'Local storage', what: 'Price alerts and alert preferences created in demo mode.' },
  { key: 'ata.membership.demo.v1', where: 'Local storage', what: 'The demo plan you chose to preview, if any (a preview only — no subscription).' },
  { key: 'ata.sidebarCollapsed.v1', where: 'Local storage', what: 'Whether the application sidebar is collapsed.' },
  { key: 'ata.membership.selected.v1', where: 'Session storage', what: 'The plan you selected, kept only for the sign-up journey in this tab.' },
  { key: 'ata.demoBannerDismissed', where: 'Session storage', what: 'That you dismissed the demo-mode banner in this tab.' },
];

export function DataStoragePage() {
  useDocumentMeta({
    title: 'Data stored in your browser',
    description: 'Exactly what this web client stores in your browser, why, and how to remove it. No cookies, analytics or trackers are used by the web client.',
    path: '/legal/data-storage',
  });
  return (
    <LegalPage
      eyebrow="Legal"
      title="Data stored in your browser"
      updated="17 October 2026"
      intro="This page lists what the web client keeps in your browser and why. It describes the website and application as built today; a full privacy policy covering server-side account data is in preparation."
    >
      <Part title="No cookies, analytics or trackers">
        <p>
          The web client sets no cookies and includes no analytics, advertising or tracking scripts. Fonts, images and background videos are served from this site, not
          from third parties.
        </p>
      </Part>
      <Part title="What is stored, and why">
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[34rem] text-left text-xs">
            <caption className="sr-only">Browser storage used by the web client</caption>
            <thead className="bg-inset text-fg-3">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">
                  Key
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Where
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Purpose
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {STORED.map((r) => (
                <tr key={r.key}>
                  <td className="num px-3 py-2 align-top text-fg">{r.key}</td>
                  <td className="px-3 py-2 align-top whitespace-nowrap">{r.where}</td>
                  <td className="px-3 py-2 align-top">{r.what}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>Session storage is cleared when you close the tab. Local storage stays until you clear it.</p>
      </Part>
      <Part title="When you use an account">
        <p>
          When the application is connected to the project’s backend, signing in and registering send your email address and password to that backend, which manages
          your account. The privacy policy for that server-side data is in preparation.
        </p>
      </Part>
      <Part title="How to remove it">
        <p>
          Sign out to remove your session; use “Clear conversation” in the assistant to delete a conversation; or clear this site’s data in your browser settings to
          remove everything listed above.
        </p>
      </Part>
    </LegalPage>
  );
}
