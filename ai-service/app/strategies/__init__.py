"""Signal strategies S1-S8 (docs/strategies/PREREG.md): one interface (``base.Candidate``), entry
rules in ``rules``, parameters in ``app/config/strategies.toml``, rollover and swap in ``swap``,
and the pre-approval candidate counts in ``counts``. Signal-time code only: nothing in this
package imports ``app.setups.labels`` or ``app.management``, so nothing here can resolve a
trade."""
