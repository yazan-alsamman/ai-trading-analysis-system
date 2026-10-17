import { useMemo, useState } from 'react';
import { usePreferences } from '@/app/contexts';
import { AssistantPanel } from '@/features/assistant/AssistantPanel';
import { createShowcaseAssistant, PUBLIC_THREAD_KEY, showcaseContext } from './showcaseAssistant';

/**
 * The assistant as offered on the public website: the app's assistant panel,
 * answering about the simulated showcase setup with the rule-based demo
 * composer. One conversation per browser, shared by the page and the launcher.
 */
export function PublicAssistant({ variant = 'page', initialQuestion, onInitialQuestionSent }: { variant?: 'page' | 'drawer'; initialQuestion?: string | null; onInitialQuestionSent?: () => void }) {
  const { timeZone } = usePreferences();
  const [shareExample, setShareExample] = useState(true);
  const service = useMemo(() => createShowcaseAssistant(), []);
  const context = useMemo(() => showcaseContext(shareExample), [shareExample]);
  return (
    <AssistantPanel
      context={context}
      shareRisk={shareExample}
      onShareRisk={setShareExample}
      variant={variant}
      timeZone={timeZone}
      service={service}
      storageKey={PUBLIC_THREAD_KEY}
      shareLabel="Use the example account"
      shareDescription="An illustrative $25,000 account at 1 % risk, so it can size the example plan."
      {...(initialQuestion !== undefined ? { initialQuestion } : {})}
      {...(onInitialQuestionSent ? { onInitialQuestionSent } : {})}
    />
  );
}
