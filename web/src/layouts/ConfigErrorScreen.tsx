import { OctagonAlert } from 'lucide-react';
import type { ConfigIssue } from '@/services/config';

/**
 * Shown instead of the app when the build configuration is invalid. The app
 * refuses to guess: running on simulated data when real data was intended
 * (or the reverse) would be worse than not starting.
 */
export function ConfigErrorScreen({ issues }: { issues: readonly ConfigIssue[] }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-5 px-4 py-10 text-fg">
      <div className="flex items-center gap-2 text-danger">
        <OctagonAlert aria-hidden className="size-5" />
        <p className="text-sm font-semibold">Configuration error</p>
      </div>
      <h1 className="text-xl font-semibold">This build of the web client is misconfigured</h1>
      <p className="text-sm text-fg-2">
        The app did not start, so it cannot show simulated data in place of the backend by mistake. Fix the values below (they are compiled into the
        build: set them in <code>web/.env.local</code> or as build arguments) and rebuild.
      </p>
      <ul className="flex flex-col gap-3">
        {issues.map((i) => (
          <li key={i.variable} className="rounded-lg border border-danger/40 bg-danger-soft px-4 py-3 text-sm">
            <p className="font-mono font-medium">
              {i.variable}=<span className="break-all">{JSON.stringify(i.value)}</span>
            </p>
            <p className="mt-1 text-fg-2">{i.message}</p>
          </li>
        ))}
      </ul>
      <p className="text-xs text-fg-3">See web/docs/BACKEND_INTEGRATION_SETUP.md, section 2.</p>
    </main>
  );
}
