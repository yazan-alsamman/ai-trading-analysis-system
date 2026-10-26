import { Smartphone, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { usePreferences, useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { IconButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { EmptyState, ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { PushDevice } from '@/domain/notificationSettings';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatRelative, MISSING } from '@/lib/format';
import { userMessage } from '@/services/errors';

const PLATFORM: Record<PushDevice['platform'], string> = { android: 'Android', ios: 'iOS', web: 'Web' };

/**
 * Devices registered for push notifications (GET /me/devices). The mobile app
 * registers itself; removing a device here stops pushes to it until the app
 * registers again.
 */
export function DevicesPanel() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const { notify } = useToast();
  const res = useResource('push-devices', (signal) => services.notificationSettings.devices({ signal }));
  const [removing, setRemoving] = useState<PushDevice | null>(null);
  const [busy, setBusy] = useState(false);

  const remove = async () => {
    if (!removing) return;
    setBusy(true);
    try {
      await services.notificationSettings.removeDevice(removing.id);
      res.setData((list) => (list ?? []).filter((d) => d.id !== removing.id));
      notify('Device removed. It gets no more push notifications unless the app registers it again.', 'info');
      setRemoving(null);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h3 className="mb-1 text-sm font-medium text-fg">Push devices</h3>
      <p className="mb-2 text-xs text-fg-3">Devices are registered by the mobile app. This website does not register for push notifications.</p>
      {res.status === 'loading' ? (
        <Loading label="Loading devices">
          <SkeletonRows rows={2} />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : !res.data?.length ? (
        <EmptyState compact icon={Smartphone} title="No devices" description="Sign in to the mobile app to receive push notifications there." />
      ) : (
        <TableRegion label="Push devices" className="rounded-md border border-line">
          <thead>
            <tr>
              <Th>Platform</Th>
              <Th>Token</Th>
              <Th>App version</Th>
              <Th>Locale</Th>
              <Th>Last seen</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {res.data.map((d) => (
              <tr key={d.id}>
                <Td>
                  <Badge>{PLATFORM[d.platform]}</Badge>
                </Td>
                <Td className="num">…{d.tokenSuffix}</Td>
                <Td>{d.appVersion ?? MISSING}</Td>
                <Td>{d.locale ?? MISSING}</Td>
                <Td title={formatDateTime(d.lastSeenAt, timeZone)}>{formatRelative(d.lastSeenAt)}</Td>
                <Td>
                  <IconButton icon={Trash2} size="sm" label={`Remove ${PLATFORM[d.platform]} device …${d.tokenSuffix}`} onClick={() => setRemoving(d)} tooltipSide="left" />
                </Td>
              </tr>
            ))}
          </tbody>
        </TableRegion>
      )}
      <ConfirmDialog
        open={removing !== null}
        title="Remove this device?"
        description="It stops receiving push notifications. The mobile app registers it again the next time it starts while you are signed in."
        confirmLabel="Remove device"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setRemoving(null)}
      />
    </div>
  );
}
