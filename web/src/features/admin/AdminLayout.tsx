import { ShieldAlert } from 'lucide-react';
import { Outlet } from 'react-router';
import { useAuth } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Page, PageHeader } from '@/components/ui/Panel';
import { EmptyState } from '@/components/ui/StateViews';
import { RouteTabs } from '@/components/ui/Tabs';
import { usePageTitle } from '@/hooks/usePageTitle';

const TABS = [
  { to: '/admin', label: 'System', end: true },
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/moderation', label: 'Moderation' },
  { to: '/admin/content', label: 'Content' },
  { to: '/admin/market-data', label: 'Market data' },
  { to: '/admin/ai', label: 'AI engine' },
  { to: '/admin/payments', label: 'Payments' },
  { to: '/admin/access', label: 'API access' },
] as const;

/**
 * The admin console (backend: /admin/*). The server refuses every admin call
 * from another role with 403; this guard only keeps non-admins from seeing an
 * empty console.
 */
export function AdminLayout() {
  usePageTitle('Admin');
  const { session } = useAuth();
  if (session?.user.role !== 'admin')
    return (
      <Page width="reading">
        <EmptyState icon={ShieldAlert} title="Admins only" description="This console is for platform administrators. Your account does not have the admin role." />
      </Page>
    );
  return (
    <Page>
      <PageHeader
        title="Admin"
        meta={<Badge tone="warning">Administrator</Badge>}
        description="Operate the platform: users, moderation, content, market data, the AI engine, payments and system health. Every action is performed by the backend and is logged there."
      />
      <RouteTabs label="Admin sections" tabs={TABS} />
      <Outlet />
    </Page>
  );
}
