import { useRouteError } from 'react-router';
import { Loading, Skeleton } from '@/components/ui/StateViews';
import { RouteErrorPage } from './ErrorPages';

export function PageFallback() {
  return (
    <Loading label="Loading page">
      <div className="flex flex-col gap-4 p-6">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-96 max-w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </Loading>
  );
}

export function ErrorBoundaryRoute() {
  return <RouteErrorPage error={useRouteError()} />;
}
