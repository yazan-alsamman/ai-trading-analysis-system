"""Trade management (docs/strategies/PREREG.md, section 7): the bar-by-bar engine for the rules
and bundles, the one-active-trade book, the fixed entry set of family C, and the post-approval
counts. Everything that needs an exit lives here; signal-time code (``app.strategies``) never
imports it."""
