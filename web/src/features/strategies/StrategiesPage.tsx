import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { useServices, useToast } from '@/app/contexts';
import { Page, PageHeader } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { SourceTag } from '@/components/ui/SourceTag';
import type { CustomStrategySummary } from '@/domain/strategies';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useResource } from '@/hooks/useResource';
import { ActivateDialog, type ActivatePreset } from './ActivateDialog';
import { ActivationsSection } from './ActivationsSection';
import { CatalogSection } from './CatalogSection';
import { CustomSection } from './CustomSection';
import { PreviewDialog, type PreviewTarget } from './PreviewDialog';
import { PublicSection } from './PublicSection';
import { errorText } from './strategyUtils';
import { SignalPlansSection } from './SignalPlansSection';

const SECTIONS = [
  { value: 'mine', label: 'My strategies' },
  { value: 'catalog', label: 'Catalog' },
  { value: 'custom', label: 'Custom' },
  { value: 'community', label: 'Community' },
  { value: 'plans', label: 'Signal plans' },
] as const;
type Section = (typeof SECTIONS)[number]['value'];
const isSection = (v: string | null): v is Section => SECTIONS.some((s) => s.value === v);

/**
 * The backend's rule-based strategy engine: platform strategies, the user's
 * activations, custom (builder/composite) strategies, published strategies
 * and the server's signal plans. Nothing here is AI output, and nothing
 * places a trade.
 */
export function StrategiesPage() {
  usePageTitle('Strategies');
  const services = useServices();
  const { notify } = useToast();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab');
  const section: Section = isSection(tab) ? tab : 'mine';

  const catalog = useResource('strategies:catalog', (signal) => services.strategies.catalog({ signal }));
  const instruments = useResource('instruments:all', (signal) => services.instruments.list({ signal }));
  const custom = useResource('strategies:custom', (signal) => services.strategies.listCustom({ signal }));
  const activations = useResource('strategies:activations', (signal) => services.strategies.listActivations({ signal }));

  // Each opening gets a fresh dialog instance (clean form state); the key changes only on open, so closing keeps focus return working.
  const [activate, setActivate] = useState<{ preset: ActivatePreset | null } | null>(null);
  const [activateKey, setActivateKey] = useState(0);
  const [preview, setPreview] = useState<PreviewTarget | null>(null);
  const [previewKey, setPreviewKey] = useState(0);

  const instrumentsReady = () => {
    if (instruments.data) return true;
    notify(instruments.status === 'error' ? errorText(instruments.error) : 'Instruments are still loading. Try again in a moment.', 'warning');
    return false;
  };
  const openActivate = (preset: ActivatePreset | null) => {
    if (!instrumentsReady()) return;
    setActivateKey((n) => n + 1);
    setActivate({ preset });
  };
  const openPreview = (target: PreviewTarget) => {
    if (!instrumentsReady()) return;
    setPreviewKey((n) => n + 1);
    setPreview(target);
  };
  const previewCustom = (s: CustomStrategySummary) => openPreview({ key: s.key, title: s.name, params: [] });

  const catalogList = catalog.data ?? [];
  const customList = custom.data ?? [];

  return (
    <Page>
      <PageHeader
        title="Strategies"
        meta={services.source === 'api' && <SourceTag kind="live" />}
        description="Rule-based strategies evaluated by the server on closed bars. Activate them on an instrument, build your own, and preview their signals on past candles. These are rules, not AI predictions, and they never place trades."
      />
      <div className="overflow-x-auto">
        <SegmentedControl
          label="Strategy sections"
          size="md"
          value={section}
          options={SECTIONS}
          onChange={(v) =>
            setParams(
              (p) => {
                const next = new URLSearchParams(p);
                if (v === 'mine') next.delete('tab');
                else next.set('tab', v);
                return next;
              },
              { replace: true },
            )
          }
        />
      </div>

      {section === 'mine' && (
        <ActivationsSection activations={activations} catalog={catalogList} custom={customList} instruments={instruments.data} onActivate={() => openActivate(null)} />
      )}
      {section === 'catalog' && (
        <CatalogSection
          catalog={catalog}
          onPreview={(d) => openPreview({ key: d.key, title: d.title, params: d.params })}
          onActivate={(d) => openActivate({ strategyKey: d.key })}
        />
      )}
      {section === 'custom' && <CustomSection custom={custom} onPreview={previewCustom} />}
      {section === 'community' && (
        <PublicSection
          onCloned={(s) =>
            custom.setData((list = []) => [
              {
                id: s.id,
                key: s.key,
                name: s.name,
                description: s.description,
                kind: s.kind,
                visibility: s.visibility,
                version: s.version,
                clonedFrom: s.clonedFrom,
                createdAt: s.createdAt,
                updatedAt: s.updatedAt,
              },
              ...list.filter((x) => x.id !== s.id),
            ])
          }
        />
      )}
      {section === 'plans' && <SignalPlansSection catalog={catalogList} custom={customList} instruments={instruments.data} />}

      {instruments.data && (
        <ActivateDialog
          key={`activate-${activateKey}`}
          open={activate !== null}
          preset={activate?.preset ?? null}
          catalog={catalogList}
          custom={customList}
          instruments={instruments.data}
          onClose={() => setActivate(null)}
          onActivated={(a) => {
            activations.setData((list = []) => [a, ...list]);
            setActivate(null);
            notify('Strategy activated. The server evaluates it on every closed bar.', 'success');
            if (section !== 'mine') setParams({}, { replace: true });
          }}
        />
      )}
      {instruments.data && (
        <PreviewDialog key={`preview-${previewKey}`} target={preview} instruments={instruments.data} onClose={() => setPreview(null)} />
      )}
    </Page>
  );
}
