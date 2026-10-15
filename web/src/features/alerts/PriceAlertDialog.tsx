import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useMemo, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Checkbox, Field, FormError, Input, Select } from '@/components/ui/Form';
import { CHANNEL_LABELS, CONDITION_LABELS, type NotificationChannel, type PriceAlert, type PriceAlertDraft } from '@/domain/alerts';
import { getInstrument, INSTRUMENTS, type InstrumentSymbol } from '@/domain/instruments';
import { formatPrice } from '@/lib/format';
import { isApiError, userMessage } from '@/services/errors';
import { priceAlertSchema, type PriceAlertFormValues } from './schemas';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Present when editing. */
  alert: PriceAlert | null;
  currentPrice: (symbol: InstrumentSymbol) => number | undefined;
  onSubmit: (draft: PriceAlertDraft) => Promise<void>;
  provenanceLabel: string | null;
}

const CHANNELS: NotificationChannel[] = ['app', 'email', 'telegram'];

function initialValues(alert: PriceAlert | null): PriceAlertFormValues {
  return alert
    ? { symbol: alert.symbol, condition: alert.condition, price: alert.price, channels: alert.channels, note: alert.note ?? '' }
    : { symbol: 'EURUSD', condition: 'crosses_above', price: Number.NaN, channels: ['app'], note: '' };
}

export function PriceAlertDialog({ open, onClose, alert, currentPrice, onSubmit, provenanceLabel }: Props) {
  const schema = useMemo(() => priceAlertSchema(currentPrice), [currentPrice]);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<PriceAlertFormValues>({
    resolver: zodResolver(schema),
    mode: 'onTouched',
    defaultValues: initialValues(alert),
  });
  const { register, handleSubmit, watch, formState, control, reset } = form;

  // Load the edited alert (or blank values) each time the dialog opens.
  useEffect(() => {
    if (open) reset(initialValues(alert));
  }, [open, alert, reset]);
  const symbol = watch('symbol');
  const inst = getInstrument(symbol);
  const current = currentPrice(symbol);

  const close = () => {
    setServerError(null);
    onClose();
  };

  const submit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await onSubmit({ ...values, note: values.note || undefined });
      close();
    } catch (error) {
      if (isApiError(error)) {
        for (const [field, messages] of Object.entries(error.fieldErrors)) {
          if (field in values) form.setError(field as keyof PriceAlertFormValues, { message: messages[0] ?? 'Invalid value' });
        }
      }
      setServerError(userMessage(error));
    }
  });

  return (
    <Dialog
      open={open}
      onClose={close}
      title={alert ? 'Edit price alert' : 'New price alert'}
      description="You will be notified when the price crosses this level."
      footer={
        <>
          <Button onClick={close} disabled={formState.isSubmitting}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="price-alert-form" loading={formState.isSubmitting}>
            {alert ? 'Save changes' : 'Create alert'}
          </Button>
        </>
      }
    >
      <form id="price-alert-form" noValidate onSubmit={submit} className="flex flex-col gap-4">
        <FormError message={serverError} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Instrument" error={formState.errors.symbol?.message}>
            {({ id, describedBy, invalid }) => (
              <Select id={id} aria-describedby={describedBy} invalid={invalid} {...register('symbol')}>
                {INSTRUMENTS.map((i) => (
                  <option key={i.symbol} value={i.symbol}>
                    {i.display}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Condition" error={formState.errors.condition?.message}>
            {({ id, describedBy, invalid }) => (
              <Select id={id} aria-describedby={describedBy} invalid={invalid} {...register('condition')}>
                {Object.entries(CONDITION_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        <Field
          label="Price level"
          error={formState.errors.price?.message}
          hint={
            current !== undefined
              ? `Current ${inst.display}: ${formatPrice(current, inst.pricePrecision)}${provenanceLabel ? ` (${provenanceLabel})` : ''}. Up to ${inst.pricePrecision} decimals.`
              : `Up to ${inst.pricePrecision} decimals.`
          }
        >
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              inputMode="decimal"
              type="number"
              step={10 ** -inst.pricePrecision}
              className="num"
              placeholder={current !== undefined ? formatPrice(current, inst.pricePrecision).replace(/,/g, '') : ''}
              {...register('price', { valueAsNumber: true })}
            />
          )}
        </Field>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">Deliver via</legend>
          <Controller
            control={control}
            name="channels"
            render={({ field }) => (
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {CHANNELS.map((c) => (
                  <Checkbox
                    key={c}
                    label={CHANNEL_LABELS[c]}
                    checked={field.value.includes(c)}
                    onChange={(e) => field.onChange(e.target.checked ? [...field.value, c] : field.value.filter((x) => x !== c))}
                  />
                ))}
              </div>
            )}
          />
          {formState.errors.channels?.message && <p className="mt-1.5 text-xs text-danger">{formState.errors.channels.message}</p>}
        </fieldset>

        <Field label="Note" optional error={formState.errors.note?.message}>
          {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} maxLength={140} {...register('note')} />}
        </Field>
      </form>
    </Dialog>
  );
}
