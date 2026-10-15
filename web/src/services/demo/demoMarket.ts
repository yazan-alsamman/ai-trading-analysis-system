import { INSTRUMENT_SYMBOLS, type InstrumentSymbol } from '@/domain/instruments';
import { bucketStart, isFxMarketOpen, type Candle, type FeedStatus, type Quote, type Timeframe } from '@/domain/market';
import {
  aggregate,
  BASE_TIMEFRAME,
  createSimulationState,
  generateHistory,
  stepPrice,
  type SimulationState,
} from '@/fixtures/marketSimulation';
import { demoScenario } from './scenario';

const HISTORY_BARS = 6000; // ≈ 62 trading days of 15m bars → ~375 bars on 4h
const BARS_24H = 96;
const TICK_MS = 1000;

interface SymbolState {
  sim: SimulationState;
  base: Candle[]; // 15m candles, last one forming
}

type TickListener = (nowSeconds: number) => void;

/**
 * In-browser simulated market (Observer pattern): one timer drives all
 * subscribers, and the timer only runs while somebody is subscribed.
 */
export class DemoMarket {
  private readonly symbols = new Map<InstrumentSymbol, SymbolState>();
  private readonly listeners = new Set<TickListener>();
  private timer: ReturnType<typeof setInterval> | undefined;

  constructor(private readonly now: () => number = () => Date.now()) {}

  private state(symbol: InstrumentSymbol): SymbolState {
    let s = this.symbols.get(symbol);
    if (!s) {
      const sim = createSimulationState(symbol);
      s = { sim, base: generateHistory(sim, Math.floor(this.now() / 1000), HISTORY_BARS) };
      this.symbols.set(symbol, s);
    }
    return s;
  }

  candles(symbol: InstrumentSymbol, timeframe: Timeframe): Candle[] {
    return aggregate(this.state(symbol).base, timeframe);
  }

  /** Latest (forming) candle for a timeframe, aggregated from the 15m tail. */
  latestCandle(symbol: InstrumentSymbol, timeframe: Timeframe): Candle | undefined {
    const base = this.state(symbol).base;
    const last = base[base.length - 1];
    if (!last) return undefined;
    const from = bucketStart(last.time, timeframe);
    let i = base.length - 1;
    while (i > 0 && (base[i - 1]?.time ?? 0) >= from) i--;
    return aggregate(base.slice(i), timeframe)[0];
  }

  quote(symbol: InstrumentSymbol): Quote {
    const base = this.state(symbol).base;
    const last = base[base.length - 1];
    const ref = base[Math.max(0, base.length - 1 - BARS_24H)];
    return {
      symbol,
      price: last?.close ?? 0,
      reference: ref?.open ?? last?.close ?? 0,
      time: this.lastTickMs ?? (last ? last.time * 1000 : this.now()),
      provenance: 'demo',
    };
  }

  quotes(): Quote[] {
    return INSTRUMENT_SYMBOLS.map((s) => this.quote(s));
  }

  private lastTickMs: number | undefined;

  marketStatus(): FeedStatus {
    return isFxMarketOpen(Math.floor(this.now() / 1000)) ? 'demo' : 'closed';
  }

  /** Advance every generated symbol by one tick. Public for tests. */
  tick(): void {
    const nowSec = Math.floor(this.now() / 1000);
    if (!isFxMarketOpen(nowSec) || demoScenario.get() === 'feed_interrupted') return;
    const bucket = bucketStart(nowSec, BASE_TIMEFRAME);
    for (const s of this.symbols.values()) {
      let last = s.base[s.base.length - 1];
      if (!last) continue;
      if (bucket > last.time) {
        last = { time: bucket, open: last.close, high: last.close, low: last.close, close: last.close, volume: 0 };
        s.base.push(last);
        s.sim.price = last.close;
      }
      // ~900 one-second ticks per 15m bar.
      const price = stepPrice(s.sim, nowSec, 900);
      last.high = Math.max(last.high, price);
      last.low = Math.min(last.low, price);
      last.close = price;
      last.volume += 1 + Math.floor(s.sim.random() * 3);
    }
    this.lastTickMs = this.now();
    this.listeners.forEach((l) => l(nowSec));
  }

  subscribe(listener: TickListener): () => void {
    this.listeners.add(listener);
    if (!this.timer) this.timer = setInterval(() => this.tick(), TICK_MS);
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0 && this.timer) {
        clearInterval(this.timer);
        this.timer = undefined;
      }
    };
  }
}
