/**
 * Licensed footage used by the public website (docs/CINEMATIC_MOTION_IMPLEMENTATION.md §4).
 *
 * Every clip is real, licensed stock footage, cut into a short seamless loop
 * by `scripts/build-media.sh` (grade baked in, no audio). The footage shows
 * people and screens for atmosphere only: the charts on those screens are not
 * the platform's data and are never presented as such.
 */
export interface Footage {
  src: string;
  /** Smaller rendition for phones (optional). */
  srcSmall?: string;
  poster: string;
  /** What the clip shows (documentation; the videos themselves are decorative). */
  subject: string;
  source: 'Coverr' | 'Mixkit';
  /** Title on the source site. */
  title: string;
  /** The exact file that was downloaded. */
  sourceUrl: string;
  licence: string;
}

const COVERR = 'Coverr licence — free for commercial use, no attribution required';
const MIXKIT = 'Mixkit Stock Video Free License — free for commercial use';

export const FOOTAGE = {
  hero: {
    src: '/media/hero-trader-desk.mp4',
    srcSmall: '/media/hero-trader-desk-sm.mp4',
    poster: '/media/hero-trader-desk.webp',
    subject: 'A trader at a desk at night, a monitor and a laptop showing candlestick charts',
    source: 'Coverr',
    title: 'A broker works with a cryptocurrency candlestick chart',
    sourceUrl: 'https://cdn.coverr.co/videos/coverr-a-broker-works-with-a-cryptocurrency-candlestick-chart-9867/1080p.mp4',
    licence: COVERR,
  },
  overload: {
    src: '/media/overload-price-board.mp4',
    poster: '/media/overload-price-board.webp',
    subject: 'An out-of-focus board of quotes and price changes',
    source: 'Coverr',
    title: 'A screen showing financial analysis of a cryptocurrency',
    sourceUrl: 'https://cdn.coverr.co/videos/coverr-a-screen-showing-financial-analysis-of-a-cryptocurrency-3490/1080p.mp4',
    licence: COVERR,
  },
  workflow: {
    src: '/media/workflow-laptop-chart.mp4',
    poster: '/media/workflow-laptop-chart.webp',
    subject: 'Hands at a laptop showing a price chart',
    source: 'Coverr',
    title: 'A businessman working on a stock market trading platform',
    sourceUrl: 'https://cdn.coverr.co/videos/coverr-a-businessman-working-on-a-stock-market-trading-platform-4862/1080p.mp4',
    licence: COVERR,
  },
  assistant: {
    src: '/media/assistant-reflection.mp4',
    poster: '/media/assistant-reflection.webp',
    subject: 'A screen reflected in a reader’s glasses (graded violet)',
    source: 'Mixkit',
    title: 'Reflection of a screen in glasses',
    sourceUrl: 'https://assets.mixkit.co/videos/221/221-1080.mp4',
    licence: MIXKIT,
  },
  method: {
    src: '/media/method-notebook.mp4',
    poster: '/media/method-notebook.webp',
    subject: 'A hand writing analysis notes in a notebook',
    source: 'Coverr',
    title: 'A trader writing analytical data in a notebook',
    sourceUrl: 'https://cdn.coverr.co/videos/coverr-a-trader-writing-analytical-data-in-a-notebook-652/1080p.mp4',
    licence: COVERR,
  },
  closing: {
    src: '/media/closing-trader-profile.mp4',
    poster: '/media/closing-trader-profile.webp',
    subject: 'A trader in profile in front of a chart, lamp-lit room',
    source: 'Coverr',
    title: 'A man analyzing the stock market',
    sourceUrl: 'https://cdn.coverr.co/videos/coverr-a-man-analyzing-the-stock-market-5128/1080p.mp4',
    licence: COVERR,
  },
} as const satisfies Record<string, Footage>;
