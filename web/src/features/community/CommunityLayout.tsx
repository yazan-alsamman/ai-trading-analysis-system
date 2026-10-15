import { Outlet } from 'react-router';
import { useServices } from '@/app/contexts';
import { DemoBadge } from '@/components/ui/Badge';
import { Page, PageHeader } from '@/components/ui/Panel';
import { RouteTabs } from '@/components/ui/Tabs';
import { usePageTitle } from '@/hooks/usePageTitle';

/** SF11 news & comments, SF12 posts, SF13 expert conversations. */
export function CommunityLayout() {
  usePageTitle('Community');
  const { source } = useServices();
  return (
    <Page width="reading">
      <PageHeader
        title="Community"
        meta={source === 'demo' && <DemoBadge label="Sample content" detail="Demo: placeholder news, people and posts. Nothing here is real." />}
        description="Market news with discussion, posts from other traders, and conversations with human trading experts."
      />
      <RouteTabs
        label="Community sections"
        tabs={[
          { to: '/community/news', label: 'News' },
          { to: '/community/posts', label: 'Posts' },
          { to: '/community/experts', label: 'Experts' },
        ]}
      />
      <Outlet />
    </Page>
  );
}
