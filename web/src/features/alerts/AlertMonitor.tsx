import { useEffect } from 'react';
import { useServices, useToast } from '@/app/contexts';
import { appEvents } from '@/app/events';
import { notificationStore } from '@/app/notifications';
import type { PriceAlert } from '@/domain/alerts';
import { crossesLevel } from '@/domain/alertRules';
import { getInstrument, type InstrumentSymbol } from '@/domain/instruments';
import { formatPrice } from '@/lib/format';

/**
 * Demo-mode price-alert engine (SF16). Watches the simulated quote stream and
 * fires active alerts when price crosses their level: marks the alert
 * triggered, adds a notification and shows a toast.
 *
 * In API mode alert evaluation belongs to the backend (it must run when the
 * browser is closed), so this component does nothing there.
 */
export function AlertMonitor() {
  const services = useServices();
  const { notify } = useToast();

  useEffect(() => {
    if (services.source !== 'demo') return;
    let alerts: PriceAlert[] = [];
    const firing = new Set<string>();
    const last = new Map<InstrumentSymbol, number>();

    const load = () =>
      services.alerts
        .list()
        .then((list) => {
          alerts = list;
        })
        .catch(() => undefined);
    void load();
    const offChanged = appEvents.on('alerts-changed', () => void load());

    const unsubscribe = services.market.subscribeQuotes({
      onStatus: () => undefined,
      onQuotes: (quotes) => {
        for (const q of quotes) {
          const previous = last.get(q.symbol);
          last.set(q.symbol, q.price);
          if (previous === undefined) continue;
          for (const alert of alerts) {
            if (alert.symbol !== q.symbol || alert.status !== 'active' || firing.has(alert.id)) continue;
            if (!crossesLevel(alert, previous, q.price)) continue;
            firing.add(alert.id);
            const inst = getInstrument(alert.symbol);
            const level = formatPrice(alert.price, inst.pricePrecision);
            const verb = alert.condition === 'crosses_above' ? 'crossed above' : 'crossed below';
            services.alerts
              .update(alert.id, { status: 'triggered', triggeredAt: Date.now() })
              .then(() => {
                notificationStore.add({
                  kind: 'price_alert',
                  title: `${inst.display} ${verb} ${level}`,
                  body: `Simulated price ${formatPrice(q.price, inst.pricePrecision)}.${alert.note ? ` Note: ${alert.note}` : ''}`,
                  provenance: q.provenance,
                  href: '/alerts',
                });
                notify(`Alert: ${inst.display} ${verb} ${level}`, 'info');
                appEvents.emit('alerts-changed');
              })
              .catch(() => firing.delete(alert.id));
          }
        }
      },
    });

    return () => {
      offChanged();
      unsubscribe();
    };
  }, [services, notify]);

  return null;
}
