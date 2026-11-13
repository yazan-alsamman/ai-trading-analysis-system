ASIA: breaks of the high and low of the Asian session (19:00 to 02:00 New York), known when the window opens at 02:00.

How a trade runs (the same for all six level strategies):

- It trades only from 02:00 to 16:00 New York time, and only the first time the price reaches the
  level that day.
- The order waits at the level as a stop order: a buy if the price comes up through it, a sell if
  it comes down through it. The trade follows the break.
- The stop is a distance D from the entry. D is 0.75 times the 14-bar ATR of the 4-hour chart.
- When the trade is one D in profit, the stop moves to the entry plus the trading cost, so the
  trade can no longer lose (except through a price gap). After that the stop trails the last confirmed 5-minute swing (minus a
  tenth of the 5-minute ATR).
- There is no fixed target. The trade ends at the trailing stop, or at 16:45 New York at the latest.
- Each strategy holds at most one open trade.
- A trade whose cost (spread and commission) is more than 5% of D is skipped.

The edge measured in the research is small: most single trades win or lose by chance, and only many
trades together show it. This is information about a rule, not advice to trade.
