import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { prefersSaveData, useReducedMotion, useSmallScreen } from './runtime';

interface Props {
  src: string;
  /** Lighter rendition used on phones. */
  srcSmall?: string;
  poster: string;
  /** Above the fold: load immediately. Otherwise nothing is fetched until the clip nears the viewport. */
  priority?: boolean;
  /** On phones, play the clip ('video') or show its poster only ('poster', the default for secondary scenes). */
  phone?: 'video' | 'poster';
  className?: string;
}

export type VideoState = 'poster' | 'idle' | 'playing' | 'paused';

/**
 * Decorative, muted, looping background footage.
 *
 *  - Plays only while on screen and while the tab is visible; paused otherwise.
 *  - Below-the-fold clips fetch nothing (`preload="none"`) until they come near the viewport.
 *  - Reduced motion, Save-Data, or `phone="poster"` on a phone → the still poster only, no video request.
 *  - If playback is refused or fails, the poster stays. Hidden from assistive technology.
 */
export function CinematicVideo({ src, srcSmall, poster, priority = false, phone = 'poster', className }: Props) {
  const reduced = useReducedMotion();
  const small = useSmallScreen();
  const [saveData] = useState(prefersSaveData);
  const [failed, setFailed] = useState(false);
  const [state, setState] = useState<VideoState>('idle');
  const ref = useRef<HTMLVideoElement>(null);
  const still = reduced || saveData || failed || (small && phone === 'poster');
  const file = small && srcSmall ? srcSmall : src;

  useEffect(() => {
    const v = ref.current;
    if (!v || still) return;
    // React does not reflect `muted` as an attribute; autoplay policies need the property set before play().
    v.muted = true;
    v.defaultMuted = true;
    let onScreen = false;
    const sync = () => {
      if (onScreen && document.visibilityState === 'visible') {
        if (v.preload === 'none') v.preload = 'auto';
        const p = v.play() as Promise<void> | undefined;
        p?.catch?.(() => setFailed(true));
      } else if (!v.paused) v.pause();
    };
    const onPlay = () => setState('playing');
    const onPause = () => setState('paused');
    v.addEventListener('playing', onPlay);
    v.addEventListener('pause', onPause);
    document.addEventListener('visibilitychange', sync);
    let io: IntersectionObserver | null = null;
    if (typeof IntersectionObserver === 'undefined') {
      onScreen = true;
      sync();
    } else {
      io = new IntersectionObserver(
        ([e]) => {
          onScreen = !!e?.isIntersecting;
          sync();
        },
        { rootMargin: '120px 0px' },
      );
      io.observe(v);
    }
    return () => {
      io?.disconnect();
      document.removeEventListener('visibilitychange', sync);
      v.removeEventListener('playing', onPlay);
      v.removeEventListener('pause', onPause);
      if (!v.paused) v.pause();
    };
  }, [still, file]);

  const cls = cn('pointer-events-none size-full object-cover select-none', className);
  if (still) {
    return <img src={poster} alt="" aria-hidden decoding="async" loading={priority ? 'eager' : 'lazy'} draggable={false} data-video-state="poster" className={cls} />;
  }
  return (
    <video
      ref={ref}
      key={file}
      src={file}
      poster={poster}
      muted
      loop
      playsInline
      disablePictureInPicture
      preload={priority ? 'auto' : 'none'}
      aria-hidden
      tabIndex={-1}
      onError={() => setFailed(true)}
      data-video-state={state}
      className={cls}
    />
  );
}
