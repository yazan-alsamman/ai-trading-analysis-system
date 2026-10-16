import { useCallback, useEffect, useRef, useState } from 'react';
import { z } from 'zod';
import { useServices } from '@/app/contexts';
import type { AssistantContext, AssistantMessage } from '@/domain/assistant';
import { localId } from '@/lib/cn';
import { readStored, removeStored, writeStored } from '@/lib/storage';
import { isAbort } from '@/services/errors';

const THREAD_KEY = 'ata.assistant.thread.v1';
const MAX_MESSAGES = 60;

const MessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant']),
  content: z.string(),
  createdAt: z.number(),
  contextUsed: z.array(z.string()).optional(),
  provider: z.enum(['demo-rules', 'remote']).optional(),
});
const ThreadSchema = z.array(MessageSchema);

export type ThreadStatus = 'idle' | 'pending' | 'error';

/**
 * One conversation, persisted in this browser only (no server history yet).
 * Supports cancellation of an in-flight reply and retry after a failure.
 */
export function useAssistantThread(context: AssistantContext) {
  const { assistant } = useServices();
  const [messages, setMessages] = useState<AssistantMessage[]>(() => readStored(THREAD_KEY, ThreadSchema, []) as AssistantMessage[]);
  const [status, setStatus] = useState<ThreadStatus>('idle');
  const [error, setError] = useState<unknown>(null);
  const controller = useRef<AbortController | null>(null);
  const contextRef = useRef(context);
  contextRef.current = context;

  useEffect(() => writeStored(THREAD_KEY, messages.slice(-MAX_MESSAGES)), [messages]);
  useEffect(() => () => controller.current?.abort(), []);

  const request = useCallback(
    async (thread: AssistantMessage[]) => {
      controller.current?.abort();
      const ctrl = new AbortController();
      controller.current = ctrl;
      setStatus('pending');
      setError(null);
      try {
        const reply = await assistant.reply(thread, contextRef.current, { signal: ctrl.signal });
        if (ctrl.signal.aborted) return;
        setMessages((m) => [
          ...m,
          { id: reply.id, role: 'assistant', content: reply.content, createdAt: reply.createdAt, contextUsed: reply.contextUsed, provider: reply.provider },
        ]);
        setStatus('idle');
      } catch (e) {
        if (isAbort(e) || ctrl.signal.aborted) {
          setStatus('idle');
          return;
        }
        setError(e);
        setStatus('error');
      }
    },
    [assistant],
  );

  const send = useCallback(
    (text: string) => {
      const content = text.trim();
      if (!content || status === 'pending') return;
      const next: AssistantMessage[] = [...messages, { id: localId('msg'), role: 'user', content, createdAt: Date.now() }];
      setMessages(next);
      void request(next);
    },
    [messages, request, status],
  );

  const retry = useCallback(() => void request(messages), [messages, request]);

  const cancel = useCallback(() => {
    controller.current?.abort();
    setStatus('idle');
  }, []);

  const clear = useCallback(() => {
    controller.current?.abort();
    setMessages([]);
    setStatus('idle');
    setError(null);
    removeStored(THREAD_KEY);
  }, []);

  return { messages, status, error, send, retry, cancel, clear, description: assistant.describe() };
}
