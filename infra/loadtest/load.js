// k6 load test of a LOCAL stack (infra/loadtest/run.sh). Never point it at production.
//
// Scenario "api": up to 200 virtual users, each with its own analyst token, picking one read at
// a time with 0.5-2 s of think time: candles (5 timeframes), indicators (5 per call), signals,
// news, posts feed, and (3% each, Y20) prediction stats, recommendations, strategy fit and the
// economic calendar. Never POST /analysis/chart-image (it would call Gemini).
// Scenario "ws": 200 WebSocket clients, each subscribed to BTC/USDT 1m candles and its own user
// topic while simulate-live rewrites the 1m candle every second; fan-out delay = receive time -
// the publisher's sent_at (same Docker host clock).

import http from 'k6/http';
import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Counter, Trend } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://nginx';
const API = `${BASE}/api/v1`;
const WS_URL = BASE.replace(/^http/, 'ws') + '/ws/market';
const HOLD = Number(__ENV.HOLD_SECONDS || 150);
const VUS = Number(__ENV.VUS || 200);
const WS_CLIENTS = Number(__ENV.WS_CLIENTS || 200);

const data = JSON.parse(open('./out/tokens.json'));
const users = new SharedArray('users', () => data.users);
const instruments = new SharedArray('instruments', () => data.instruments);
const live = data.instruments.find((i) => i.symbol === (__ENV.LIVE_SYMBOL || 'BTC/USDT'));

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h'];
const INDICATORS = [
  { name: 'rsi', params: { length: 14 } },
  { name: 'ema', params: { length: 20 } },
  { name: 'macd', params: {} },
  { name: 'bollinger', params: {} },
  { name: 'atr', params: {} },
];
const ENDPOINTS = [
  'candles', 'indicators', 'signals', 'news', 'posts',
  'prediction_stats', 'recommendations', 'reco_strategies', 'calendar',
];
const WEIGHTS = [0.31, 0.18, 0.13, 0.13, 0.13, 0.03, 0.03, 0.03, 0.03];

const latency = {};
const errors = {};
const limited = {};
for (const ep of ENDPOINTS) {
  latency[ep] = new Trend(`lat_${ep}`, true);
  errors[ep] = new Counter(`err_${ep}`);
  limited[ep] = new Counter(`r429_${ep}`);
}
const fanout = new Trend('ws_fanout_delay', true);
const wsCandles = new Counter('ws_candle_messages');
const wsErrors = new Counter('ws_errors');
const wsConnected = new Counter('ws_connected');

export const options = {
  summaryTrendStats: ['avg', 'min', 'med', 'p(95)', 'p(99)', 'max', 'count'],
  scenarios: {
    api: {
      executor: 'ramping-vus',
      exec: 'api',
      stages: [
        { duration: '30s', target: VUS },
        { duration: `${HOLD}s`, target: VUS },
        { duration: '15s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
    ws: {
      executor: 'per-vu-iterations',
      exec: 'socket',
      vus: WS_CLIENTS,
      iterations: 1,
      maxDuration: `${HOLD + 90}s`,
    },
  },
};

function pick() {
  let r = Math.random();
  for (let i = 0; i < ENDPOINTS.length; i++) {
    if ((r -= WEIGHTS[i]) < 0) return ENDPOINTS[i];
  }
  return ENDPOINTS[0];
}

function any(list) {
  return list[Math.floor(Math.random() * list.length)];
}

export function api() {
  const user = users[(__VU - 1) % users.length];
  const params = { headers: { Authorization: `Bearer ${user.token}` }, tags: {} };
  const ep = pick();
  const iid = any(instruments).id;
  const tf = any(TIMEFRAMES);
  params.tags.ep = ep;
  let res;
  if (ep === 'candles') {
    res = http.get(`${API}/market/instruments/${iid}/candles?timeframe=${tf}&limit=500`, params);
  } else if (ep === 'indicators') {
    params.headers['Content-Type'] = 'application/json';
    const body = JSON.stringify({ timeframe: tf, limit: 500, indicators: INDICATORS });
    res = http.post(`${API}/market/instruments/${iid}/indicators`, body, params);
  } else if (ep === 'signals') {
    res = http.get(`${API}/signals?limit=50`, params);
  } else if (ep === 'news') {
    res = http.get(`${API}/news?limit=30`, params);
  } else if (ep === 'posts') {
    res = http.get(`${API}/posts?limit=20`, params);
  } else if (ep === 'prediction_stats') {
    res = http.get(`${API}/predictions/stats`, params);
  } else if (ep === 'recommendations') {
    res = http.get(`${API}/me/recommendations?limit=20`, params);
  } else if (ep === 'reco_strategies') {
    res = http.get(`${API}/recommendations/strategies?instrument_id=${iid}&timeframe=${tf}`, params);
  } else {
    res = http.get(`${API}/calendar/events?min_impact=medium`, params);
  }
  latency[ep].add(res.timings.duration);
  if (res.status === 429) limited[ep].add(1);
  else if (res.status !== 200) errors[ep].add(1);
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.5 + Math.random() * 1.5);
}

export function socket() {
  const user = users[(__VU - 1) % users.length];
  sleep(Math.random() * 20); // connect over 20 s, like a crowd opening the app
  const holdMs = HOLD * 1000;
  const res = ws.connect(`${WS_URL}?token=${user.token}`, null, (s) => {
    s.on('open', () => {
      wsConnected.add(1);
      s.send(JSON.stringify({ op: 'subscribe', topic: 'candles', instrument_id: live.id, timeframe: '1m' }));
      s.send(JSON.stringify({ op: 'subscribe', topic: 'user', user_id: user.id }));
      s.setInterval(() => s.send('{"op":"ping"}'), 20000);
      s.setTimeout(() => s.close(), holdMs);
    });
    s.on('message', (raw) => {
      const msg = JSON.parse(raw);
      if (msg.type === 'candle') {
        wsCandles.add(1);
        fanout.add(Date.now() - msg.sent_at);
      } else if (msg.type === 'error') {
        wsErrors.add(1);
      }
    });
    s.on('error', () => wsErrors.add(1));
  });
  check(res, { 'ws 101': (r) => r && r.status === 101 });
}

export function handleSummary(summary) {
  return { 'out/summary.json': JSON.stringify(summary, null, 2) };
}
