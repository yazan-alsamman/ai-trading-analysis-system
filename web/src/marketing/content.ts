/** Public-site content shared across sections (kept out of component files). */

export const PUBLIC_NAV = [
  { to: '/#platform', label: 'Platform' },
  { to: '/#how-it-works', label: 'How it works' },
  { to: '/#risk', label: 'Risk management' },
  { to: '/#methodology', label: 'Methodology' },
  { to: '/membership', label: 'Membership' },
  { to: '/#faq', label: 'FAQ' },
] as const;

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

