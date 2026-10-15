import { FlaskConical } from 'lucide-react';
import type { ReactNode } from 'react';
import { useServices } from '@/app/contexts';

export function AuthCard({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  const { source } = useServices();
  return (
    <div className="rounded-lg border border-line bg-surface p-6 shadow-float">
      <h1 className="text-lg font-semibold text-fg">{title}</h1>
      <p className="mt-1 text-sm text-fg-2">{subtitle}</p>
      {source === 'demo' && (
        <p className="mt-4 flex items-start gap-2 rounded-md border border-demo/40 bg-demo-soft px-3 py-2 text-xs text-fg">
          <FlaskConical aria-hidden className="mt-0.5 size-3.5 shrink-0 text-demo" />
          Demo mode: no backend is connected. Credentials are not sent anywhere or verified, and the password is never stored. A local demo session is created.
        </p>
      )}
      <div className="mt-5">{children}</div>
      <div className="mt-5 border-t border-line pt-4 text-center text-sm text-fg-2">{footer}</div>
    </div>
  );
}
