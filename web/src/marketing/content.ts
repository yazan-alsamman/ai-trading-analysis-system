/** Public-site content shared across sections (kept out of component files). */

export const PUBLIC_NAV = [
  { to: '/#platform', label: 'Platform' },
  { to: '/#how-it-works', label: 'How it works' },
  { to: '/#methodology', label: 'Methodology' },
  { to: '/ai-assistant', label: 'Assistant' },
  { to: '/about', label: 'About' },
  { to: '/membership', label: 'Membership' },
] as const;

export interface FooterLink {
  to: string;
  label: string;
  /** Shown only when the app runs on simulated data (the live demo needs no account). */
  demoOnly?: boolean;
}

/**
 * Footer navigation. Every `to` is an existing route or an anchor on one
 * (checked by marketing/footer.test.tsx and e2e/round6.spec.ts). Terms of
 * service, privacy policy and contact are deliberately absent: none exists yet
 * (docs/PUBLIC_SITE_CONTENT.md §4).
 */
export const FOOTER_GROUPS: readonly { title: string; links: readonly FooterLink[]; note?: string }[] = [
  {
    title: 'Platform',
    links: [
      { to: '/#platform', label: 'The seven modules' },
      { to: '/#how-it-works', label: 'How it works' },
      { to: '/#anatomy', label: 'Anatomy of a setup' },
      { to: '/#risk', label: 'Risk management' },
      { to: '/ai-assistant', label: 'Research assistant' },
      { to: '/#methodology', label: 'Methodology' },
      { to: '/overview', label: 'Open the live demo', demoOnly: true },
    ],
  },
  {
    title: 'Company',
    links: [
      { to: '/about', label: 'About' },
      { to: '/about#approach-ai', label: 'Our approach to AI' },
      { to: '/about#risk-transparency', label: 'Risk and transparency' },
      { to: '/#faq', label: 'FAQ' },
    ],
    note: 'A graduation project. No public contact address has been published yet.',
  },
  {
    title: 'Membership',
    links: [
      { to: '/membership#plans', label: 'Plans' },
      { to: '/membership#compare', label: 'Compare features' },
      { to: '/membership#membership-faq', label: 'Membership FAQ' },
      { to: '/login', label: 'Sign in' },
      { to: '/register', label: 'Create account' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { to: '/legal/risk-disclosure', label: 'Risk disclosure' },
      { to: '/legal/data-storage', label: 'Data stored in your browser' },
    ],
    note: 'Terms of service and privacy policy: in preparation, not yet published.',
  },
];

export interface FaqItem {
  q: string;
  a: string;
}

export const GENERAL_FAQ: FaqItem[] = [
  { q: 'Does the platform place trades for me?', a: 'No. It is analysis and decision support only. It never places, modifies or closes a trade, and there are no execution controls anywhere in the product.' },
  {
    q: 'Is the AI output a prediction?',
    a: 'It is a probability with a definition: the estimated chance that the take-profit is reached before the stop-loss within the model’s horizon. It can be wrong, and every output shows its evidence, what could invalidate it and what is missing.',
  },
  {
    q: 'Is the market data live?',
    a: 'Not yet. In demo mode prices, model outputs and statistics are simulated in your browser and labelled “Simulated” everywhere. Live data arrives with the backend integration.',
  },
  { q: 'Do I need an account to explore?', a: 'No. This website explains every module, and the live demo opens the full application with simulated data — no sign-in required in demo mode.' },
  {
    q: 'Where do the results on this site come from?',
    a: 'From simulated predictions generated in the browser, to demonstrate how results are evaluated. No verified live results exist yet, and none are claimed.',
  },
  {
    q: 'What is stored about me?',
    a: 'Your risk and signal profiles, workspaces and demo membership are stored in this browser. In demo mode, signing in creates a local session; credentials are not sent anywhere and the password is never stored.',
  },
];

export const MEMBERSHIP_FAQ: FaqItem[] = [
  { q: 'What does each plan cost?', a: 'Pricing has not been set by the project owner, so every plan shows “Pricing to be announced”. No price on this site is an offer.' },
  {
    q: 'Can I subscribe today?',
    a: 'Not yet: no billing service is connected. You can choose a plan, create an account and — in demo mode — preview the plan as a clearly labelled demo membership. Nothing is charged.',
  },
  { q: 'What does “Demo data” mean in the comparison?', a: 'The feature works in the interface but runs on simulated market data and model output until the backend is connected.' },
  { q: 'Will my plan limit what I can see?', a: 'In the demo, a selected plan changes which modules appear as included. This is a preview of the experience, not access control: real enforcement will happen on the server.' },
  { q: 'Why are risk tools and analytics in every plan?', a: 'Because sizing risk correctly and seeing how the model has performed should never be a premium feature.' },
];

