import { useEffect } from 'react';

const APP = 'AI Trading Assistance';

/** Sets a descriptive document title per page (WCAG 2.4.2). */
export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · ${APP}`;
    return () => {
      document.title = APP;
    };
  }, [title]);
}
