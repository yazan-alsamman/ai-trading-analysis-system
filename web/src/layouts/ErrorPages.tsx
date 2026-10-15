import { Compass, OctagonAlert } from 'lucide-react';
import { isRouteErrorResponse, Link } from 'react-router';

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 p-6 text-center">
      <Compass aria-hidden className="size-7 text-fg-3" />
      <h1 className="text-lg font-semibold text-fg">Page not found</h1>
      <p className="max-w-sm text-sm text-fg-2">The address does not match any page in AI Trading Assistance.</p>
      <Link to="/workspace" className="mt-2 inline-flex h-9 items-center rounded-md bg-accent px-3.5 text-sm font-medium text-accent-fg hover:bg-accent-hover">
        Go to workspace
      </Link>
    </div>
  );
}

/** Last-resort boundary for render errors and failed lazy chunks. */
export function RouteErrorPage({ error }: { error: unknown }) {
  const detail = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : error instanceof Error ? error.message : 'Unknown error';
  const chunkFailed = error instanceof Error && /dynamically imported module|Loading chunk/i.test(error.message);
  return (
    <div role="alert" className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-canvas p-6 text-center">
      <OctagonAlert aria-hidden className="size-7 text-danger" />
      <h1 className="text-lg font-semibold text-fg">{chunkFailed ? 'Could not load this page' : 'Something went wrong'}</h1>
      <p className="max-w-md text-sm text-fg-2">
        {chunkFailed ? 'Part of the application could not be downloaded. Check your connection and reload.' : 'An unexpected error occurred while displaying this page.'}
      </p>
      <p className="num max-w-md text-xs break-words text-fg-3">{detail}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex h-9 items-center rounded-md bg-accent px-3.5 text-sm font-medium text-accent-fg hover:bg-accent-hover"
        >
          Reload
        </button>
        <Link to="/workspace" className="inline-flex h-9 items-center rounded-md border border-line-strong px-3.5 text-sm font-medium text-fg hover:bg-hover">
          Go to workspace
        </Link>
      </div>
    </div>
  );
}
