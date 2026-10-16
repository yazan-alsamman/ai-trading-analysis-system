import { describe, expect, it } from 'vitest';
import { numberError, parseDecimal, usable } from './parse';

describe('decimal input parsing', () => {
  it('accepts plain and thousands-separated numbers', () => {
    expect(parseDecimal('2350.5')).toBe(2350.5);
    expect(parseDecimal(' 2,350.50 ')).toBe(2350.5);
    expect(parseDecimal('.5')).toBe(0.5);
    expect(parseDecimal('10')).toBe(10);
  });

  it('treats empty as "not entered" and garbage as invalid — never as 0', () => {
    expect(parseDecimal('')).toBeNull();
    expect(parseDecimal(null)).toBeNull();
    expect(parseDecimal('1.2.3')).toBeNaN();
    expect(parseDecimal('12abc')).toBeNaN();
    expect(usable(parseDecimal('abc'))).toBe(false);
    expect(usable(parseDecimal('0'))).toBe(false);
  });

  it('produces plain-language field errors', () => {
    expect(numberError(null, { required: true, label: 'an entry price' })).toBe('Enter an entry price.');
    expect(numberError(Number.NaN, { label: 'capital' })).toBe('Enter capital as a number, e.g. 2350.5.');
    expect(numberError(150, { max: 100, label: 'risk per trade' })).toBe('Risk per trade must be at most 100.');
    expect(numberError(2.5, { integer: true, label: 'open positions' })).toBe('Use a whole number for open positions.');
    expect(numberError(5, { min: 0, label: 'x' })).toBeUndefined();
  });
});
