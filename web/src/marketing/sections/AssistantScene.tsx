import { Bot } from 'lucide-react';
import { useRef, type CSSProperties } from 'react';
import { Markdown } from '@/components/ui/Markdown';
import { SourceTag } from '@/components/ui/SourceTag';
import { CinematicVideo } from '@/motion/CinematicVideo';
import { Reveal, RevealText } from '@/motion/Reveal';
import { useInView } from '@/motion/runtime';
import { FOOTAGE } from '../media';
import { buildShowcase } from '../showcase';

const QUESTION = 'What would invalidate this projection?';
const at = (ms: number) => ({ '--at': `${ms}ms` }) as CSSProperties;

/**
 * Scene: the AI assistant, in violet (the colour the platform reserves for
 * model output). The question is asked, the context it may use lights up and
 * connects to the answer, and the reply arrives block by block. The reply is
 * the demo assistant's actual rule-based output — no language model is
 * connected, and the scene says so.
 */
export function AssistantScene() {
  const s = buildShowcase();
  const chat = useRef<HTMLDivElement>(null);
  const inView = useInView(chat);
  const blocks = s.assistant.content.split(/\n\s*\n/).filter((b) => b.trim());
  const used = s.assistant.contextUsed.slice(0, 4);
  const replyAt = 1700;

  return (
    <section id="assistant" data-section aria-labelledby="assistant-title" className="violet-scene relative isolate overflow-hidden border-b border-line">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[minmax(0,1fr)] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)] lg:items-center">
        <div>
          <p className="eyebrow mb-3">07 · AI assistant</p>
          <RevealText as="h2" id="assistant-title" className="display text-d3 text-fg sm:text-d2" lines={['Ask why.', <em key="e">Get the evidence.</em>]} />
          <Reveal as="p" delay={150} className="mt-4 max-w-md text-md text-fg-2">
            Ask what the model saw, what would prove it wrong, or what a trade means for your capital. It answers only from the data on your screen, and names what it used.
          </Reveal>
          <Reveal variant="scale" delay={200} className="relative mt-10 hidden aspect-[4/3] overflow-hidden rounded-2xl border border-forecast/30 md:block">
            <CinematicVideo {...FOOTAGE.assistant} />
            <div className="footage-veil absolute inset-0" aria-hidden />
          </Reveal>
        </div>

        <Reveal variant="rise" className="rounded-2xl border border-forecast/30 bg-surface/95 p-5 shadow-float">
          <div className="flex items-center gap-2">
            <span aria-hidden className="inline-flex size-7 items-center justify-center rounded-full border border-forecast/40 bg-forecast-soft text-forecast">
              <Bot className="size-3.5" />
            </span>
            <p className="text-md font-semibold text-fg">Assistant</p>
            <SourceTag kind="demo" label="Rule-based demo" detail="No language model is connected. These are the demo assistant's actual, rule-based answers." className="ml-auto" />
          </div>

          <div ref={chat} data-play={inView} className="mt-5 flex flex-col gap-4">
            <p className="m-in ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-selected px-3.5 py-2 text-sm text-fg" style={at(150)}>
              {QUESTION}
            </p>

            {/* The context the answer may draw on, connected to the reply. */}
            <div>
              <p className="m-in text-xs text-fg-3" style={at(500)}>
                Drawing on what is on screen
              </p>
              <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Context the answer used">
                {used.map((u, i) => (
                  <li key={u} className="m-in rounded-lg border border-forecast/30 bg-forecast-soft px-2.5 py-1.5 text-xs text-fg" style={at(650 + i * 100)}>
                    {u}
                  </li>
                ))}
              </ul>
              <svg aria-hidden viewBox="0 0 1000 40" preserveAspectRatio="none" className="hidden h-8 w-full sm:block">
                {used.map((u, i) => (
                  <path
                    key={u}
                    d={`M${((i + 0.5) / used.length) * 1000} 0 C${((i + 0.5) / used.length) * 1000} 26, 18 14, 18 40`}
                    fill="none"
                    pathLength={1}
                    vectorEffect="non-scaling-stroke"
                    className="m-draw stroke-forecast"
                    strokeOpacity="0.55"
                    strokeWidth="1"
                    style={{ '--at': `${1050 + i * 90}ms`, '--dur': '600ms', '--len': 1 } as CSSProperties}
                  />
                ))}
              </svg>
            </div>

            <div className="flex gap-3">
              <span aria-hidden className="m-in mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-full border border-forecast/40 bg-forecast-soft text-forecast" style={at(1300)}>
                <Bot className="size-3.5" />
              </span>
              <div className="relative min-w-0 flex-1">
                {/* Typing indicator: three finite pulses, then it gives way to the reply. */}
                <span aria-hidden className="typing absolute top-2 left-0 flex gap-1" style={at(replyAt)}>
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="typing-dot size-1.5 rounded-full bg-forecast" style={{ '--i': i } as CSSProperties} />
                  ))}
                </span>
                <div className="flex flex-col gap-2.5">
                  {blocks.map((b, i) => (
                    <div key={i} className="reply-block" style={at(replyAt + i * 380)}>
                      <Markdown source={b} className="text-xs leading-5" />
                    </div>
                  ))}
                </div>
                <p className="reply-block mt-3 text-xs text-fg-3" style={at(replyAt + blocks.length * 380)}>
                  Rule-based, not a language model · used: {s.assistant.contextUsed.join(', ')}
                </p>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
