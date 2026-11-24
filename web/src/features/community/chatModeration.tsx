import { Ban, Check, Pencil, ShieldCheck, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { useServices, useToast } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Button, IconButton } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/Dialog';
import { Textarea } from '@/components/ui/Form';
import type { ChatMessage } from '@/domain/community';
import type { ConversationDetail } from '@/domain/social';
import { userMessage } from '@/services/errors';

/** docs/chat.md: the sender may edit within 15 minutes (CHAT_EDIT_WINDOW_MINUTES). */
const EDIT_WINDOW_MS = 15 * 60_000;

const STATUS_LABEL: Record<ConversationDetail['status'], string> = { open: 'Open', closed: 'Closed', blocked: 'Blocked' };

/**
 * Backend mode: the conversation's state and blocking. Either side may block;
 * a blocked conversation takes no new messages until the side that blocked
 * unblocks it.
 */
export function ChatModerationBar({ conversation, onChange }: { conversation: ConversationDetail; onChange: (c: ConversationDetail) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const toggle = async (block: boolean) => {
    setBusy(true);
    try {
      const next = block ? await services.social.blockConversation(conversation.id) : await services.social.unblockConversation(conversation.id);
      onChange(next);
      notify(block ? 'Conversation blocked. No new messages can be sent.' : 'Conversation unblocked.', 'info');
      setConfirming(false);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };

  const blocked = conversation.status === 'blocked';
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2 text-xs text-fg-2">
      <Badge tone={blocked ? 'warning' : 'neutral'}>{STATUS_LABEL[conversation.status]}</Badge>
      {blocked && !conversation.blockedByMe && <span>The other side blocked this conversation.</span>}
      {!conversation.canSend && conversation.readOnlyReason && !blocked && <span>{conversation.readOnlyReason}</span>}
      <span className="ml-auto">
        {conversation.blockedByMe ? (
          <Button size="sm" variant="ghost" icon={ShieldCheck} loading={busy} onClick={() => void toggle(false)}>
            Unblock
          </Button>
        ) : (
          !blocked && (
            <Button size="sm" variant="ghost" icon={Ban} onClick={() => setConfirming(true)}>
              Block
            </Button>
          )
        )}
      </span>
      <ConfirmDialog
        open={confirming}
        title="Block this conversation?"
        description={`No new messages can be sent by either side until you unblock it. ${conversation.other.name} is not told why. Your subscription is not changed.`}
        confirmLabel="Block"
        busy={busy}
        onConfirm={() => void toggle(true)}
        onCancel={() => setConfirming(false)}
      />
    </div>
  );
}

/**
 * Edit (within 15 minutes) and delete for one of your own messages. The server
 * keeps a tombstone for a deleted message; this view simply removes it.
 */
export function OwnMessageActions({ message, now, onEdited, onDeleted }: { message: ChatMessage; now: number; onEdited: (m: ChatMessage) => void; onDeleted: (id: string) => void }) {
  const services = useServices();
  const { notify } = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.body);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const editable = now - message.sentAt < EDIT_WINDOW_MS;

  const save = async () => {
    const body = draft.trim();
    if (!body || body === message.body) return setEditing(false);
    setBusy(true);
    try {
      const edited = await services.social.editMessage(message.id, body);
      onEdited({ ...message, body: edited.body ?? body, ...(edited.editedAt !== null ? { editedAt: edited.editedAt } : {}) });
      setEditing(false);
    } catch (e) {
      notify(userMessage(e), 'danger');
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    setBusy(true);
    try {
      await services.social.deleteMessage(message.id);
      onDeleted(message.id);
    } catch (e) {
      notify(userMessage(e), 'danger');
      setBusy(false);
    }
  };

  if (editing)
    return (
      <form
        className="mt-1 flex w-full max-w-[85%] items-end gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <label className="sr-only" htmlFor={`edit-${message.id}`}>
          Edit message
        </label>
        <Textarea id={`edit-${message.id}`} rows={2} className="min-h-9" value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
        <IconButton icon={Check} type="submit" label="Save edit" size="sm" disabled={busy} tooltipSide="left" />
        <IconButton icon={X} label="Cancel edit" size="sm" disabled={busy} onClick={() => setEditing(false)} tooltipSide="left" />
      </form>
    );

  return (
    <span className="flex items-center gap-0.5">
      {editable && (
        <IconButton
          icon={Pencil}
          label="Edit message"
          size="sm"
          onClick={() => {
            setDraft(message.body);
            setEditing(true);
          }}
          tooltipSide="left"
        />
      )}
      <IconButton icon={Trash2} label="Delete message" size="sm" onClick={() => setConfirming(true)} tooltipSide="left" />
      <ConfirmDialog
        open={confirming}
        title="Delete this message?"
        description="It is removed for both of you. The conversation keeps a note that a message was deleted."
        confirmLabel="Delete message"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setConfirming(false)}
      />
    </span>
  );
}
