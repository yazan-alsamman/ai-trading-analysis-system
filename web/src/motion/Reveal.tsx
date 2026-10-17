import { useRef, type CSSProperties, type ElementType, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { useInView } from './runtime';
import { STAGGER } from './tokens';

export type RevealVariant = 'rise' | 'fade' | 'scale' | 'blur' | 'left' | 'right';

interface RevealProps {
  children: ReactNode;
  as?: ElementType;
  variant?: RevealVariant;
  /** Extra delay in ms. */
  delay?: number;
  /** Position in a staggered group (adds index × stagger). */
  index?: number;
  stagger?: number;
  className?: string;
  /** Re-hide when leaving the viewport (default: reveal once). */
  repeat?: boolean;
  id?: string;
}

/**
 * Viewport-triggered entrance. Uses opacity + transform (+ a light blur for
 * `blur`) via CSS transitions in styles/motion.css. Content is visible when
 * motion is reduced or IntersectionObserver is unavailable.
 */
export function Reveal({ children, as: Tag = 'div', variant = 'rise', delay = 0, index = 0, stagger = STAGGER.items, className, repeat = false, id }: RevealProps) {
  const ref = useRef<HTMLElement>(null);
  const shown = useInView(ref, { once: !repeat });
  return (
    <Tag ref={ref} id={id} data-reveal={variant} data-shown={shown} className={className} style={{ '--reveal-delay': `${delay + index * stagger}ms` } as CSSProperties}>
      {children}
    </Tag>
  );
}

/**
 * Editorial line-by-line mask reveal. Each line slides up inside its own
 * clipping box. `trigger="mount"` plays on first paint (hero); `"view"` waits
 * for the viewport. The text stays a single heading for assistive tech.
 */
export function RevealText({
  lines,
  as: Tag = 'h2',
  className,
  delay = 0,
  trigger = 'view',
  id,
}: {
  lines: ReactNode[];
  as?: ElementType;
  className?: string;
  delay?: number;
  trigger?: 'mount' | 'view';
  id?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  const shown = trigger === 'mount' ? true : inView;
  return (
    <Tag ref={ref} id={id} className={cn('reveal-lines', className)} data-shown={shown} data-trigger={trigger}>
      {lines.map((line, i) => (
        <span key={i} className="reveal-line">
          <span className="reveal-line-inner" style={{ '--line-delay': `${delay + i * STAGGER.lines}ms` } as CSSProperties}>
            {line}
          </span>
        </span>
      ))}
    </Tag>
  );
}
