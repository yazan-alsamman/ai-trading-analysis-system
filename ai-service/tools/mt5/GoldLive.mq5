//+------------------------------------------------------------------+
//| GoldLive.mq5: gold v1 live (ai-service/docs/strategies/GOLD_V1.md)|
//| LVL4H and PIVOT level breaks with M8 management, computed from    |
//| the terminal's bars, for the demo account. The shadow strategies   |
//| PIVW, ASIA and PWHL (GOLD_SHADOW.md) run beside v1 with their own  |
//| magic numbers and ShadowRiskPct; MaxOpenRiskPct caps the risk of   |
//| every open trade and order of the EA together.                     |
//|                                                                   |
//| Expert Advisor on GOLD (any chart timeframe), a hedging account.  |
//| Writes <Common>/Files/<LogFile>: every signal, fill, SL move and  |
//| exit, read by python -m app research gold-live check.             |
//|                                                                   |
//| Bars: the closed M5 bars; 1h, 4h and trading days (17:00-17:00)   |
//| are built from them on the New York clock, as the research store  |
//| does, so the DST weeks where the server and New York disagree     |
//| match too. The server clock is Europe/Athens.                     |
//|                                                                   |
//| At each new M5 bar: M8 on the open trades with the bar just       |
//| closed, the horizon exits, then for each strategy without an open |
//| trade a stop order at every level not yet touched today, valid    |
//| for this bar (at market when price is already through it). On     |
//| each tick: the other orders of a strategy go when one fills, an   |
//| SL the broker refused is watched, and trades close at 16:45 New   |
//| York. SignalsOnly: log the signals, place nothing.                |
//+------------------------------------------------------------------+
#include <Trade\Trade.mqh>

input double RiskPct     = 0.5;                  // % of equity a trade (fixed fractional)
input double FixedLots   = 0.0;                  // > 0: this size instead (tests)
input bool   TradeLVL4H  = true;
input bool   TradePIVOT  = true;
input bool   TradePIVW   = true;                 // shadow: R1 / S1 with LVL4H's distance and cap
input bool   TradeASIA   = true;                 // shadow: the Asian range, 19:00-02:00 New York
input bool   TradePWHL   = true;                 // shadow: the previous week's high and low
input double ShadowRiskPct  = 0.25;              // % of equity a shadow trade
input double MaxOpenRiskPct = 2.0;               // cap on the open risk of the EA (0: none; tests)
input bool   SignalsOnly = false;                // log the signals, place nothing
input long   MagicBase   = 20261106;             // LVL4H base, PIVOT +1, PIVW +2, ASIA +3, PWHL +4
input string LogFile     = "gold_live_log.csv";  // in <Common>/Files
input int    Bars5m      = 8000;                 // M5 history for the ATRs (about 28 days)

#define NS 5
#define NK 4
string   SNAME[NS]   = {"LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL"};
string   KNAME[NS][NK] = {{"PDH", "PDL", "5DH", "5DL"}, {"R1", "S1", "", ""}, {"R1", "S1", "", ""},
                          {"ASH", "ASL", "", ""}, {"PWH", "PWL", "", ""}};
int      NKINDS[NS]  = {4, 2, 2, 2, 2};
int      HORIZON[NS] = {200, 48, 200, 200, 200};
const double LVL_MULT   = 0.75;
const double LVL_CAP    = 0.05;
const double COMMISSION = 0.07;   // $ per oz, round trip
const int    WIN_FROM   = 120;    // New York minutes at the bar open
const int    WIN_TO     = 960;
const int    END_MIN    = 16 * 60 + 45;

CTrade trade;
datetime last_bar = 0;

// --- clocks ------------------------------------------------------------------------------------

datetime Make(const int y, const int m, const int d, const int h)
  {
   MqlDateTime t = {};
   t.year = y; t.mon = m; t.day = d; t.hour = h;
   return StructToTime(t);
  }

int DayOfWeek(const int y, const int m, const int d)
  {
   MqlDateTime t;
   TimeToStruct(Make(y, m, d, 0), t);
   return t.day_of_week;
  }

int NthSunday(const int y, const int m, const int n)
  {
   int first = 1 + (7 - DayOfWeek(y, m, 1)) % 7;
   return first + 7 * (n - 1);
  }

int LastSunday(const int y, const int m)
  {
   MqlDateTime t;
   TimeToStruct(Make(m == 12 ? y + 1 : y, m == 12 ? 1 : m + 1, 1, 0) - 86400, t);
   return t.day - t.day_of_week;
  }

// The summer-time switches of one year, cached: the bars of a refresh fall in one or two years.
datetime yr_from = 0, yr_to = 0, eu_from, eu_to, us_from, us_to;

void Switches(const datetime utc)
  {
   if(utc >= yr_from && utc < yr_to)
      return;
   MqlDateTime t;
   TimeToStruct(utc, t);
   int y = t.year;
   yr_from = Make(y, 1, 1, 0);
   yr_to   = Make(y + 1, 1, 1, 0);
   eu_from = Make(y, 3, LastSunday(y, 3), 1);    // last Sunday of March 01:00 UTC
   eu_to   = Make(y, 10, LastSunday(y, 10), 1);  // last Sunday of October 01:00 UTC
   us_from = Make(y, 3, NthSunday(y, 3, 2), 7);  // second Sunday of March 07:00 UTC
   us_to   = Make(y, 11, NthSunday(y, 11, 1), 6); // first Sunday of November 06:00 UTC
  }

bool EuSummer(const datetime utc) { Switches(utc); return utc >= eu_from && utc < eu_to; }
bool UsSummer(const datetime utc) { Switches(utc); return utc >= us_from && utc < us_to; }

datetime ServerToUtc(const datetime s)
  {
   datetime u = s - 3 * 3600;
   return EuSummer(u) ? u : s - 2 * 3600;
  }

datetime UtcToNy(const datetime u) { return u - (UsSummer(u) ? 4 : 5) * 3600; }

// Day numbers since 1970-01-01 (a Thursday) on the New York clock.
long DayKey(const datetime ny) { return (long)(ny + 7 * 3600) / 86400; }  // the trading day, 17:00-17:00
long Week(const long key)      { return (key + 3) / 7; }  // weeks Monday to Sunday of a day number
long CalDay(const datetime ny) { return (long)ny / 86400; }
int  NyMin(const datetime ny)  { return (int)(((long)ny % 86400) / 60); }
int  NyDow(const datetime ny)  { return (int)(((long)ny / 86400 + 4) % 7); }  // 0 = Sunday

// --- bars and series ---------------------------------------------------------------------------

int      NB = 0;
datetime b_srv[], b_utc[], b_ny[];
double   b_o[], b_h[], b_l[], b_c[], atr5[], swl[], swh[];

struct Bkt { long key; datetime close_utc; double h, l, c, atr; };
Bkt H1[], H4[];
struct Day { long key; double h, l, c; };
Day D1[];

void Wilder(Bkt &b[])
  {
   for(int k = 0; k < ArraySize(b); k++)
     {
      double tr = b[k].h - b[k].l;
      if(k > 0)
         tr = MathMax(tr, MathMax(MathAbs(b[k].h - b[k - 1].c), MathAbs(b[k].l - b[k - 1].c)));
      b[k].atr = k == 0 ? tr : b[k - 1].atr + (tr - b[k - 1].atr) / 14.0;
     }
  }

// Buckets of ``len`` seconds on the shifted New York clock (New York + 7 h puts 17:00 at midnight).
void Buckets(Bkt &b[], const int len)
  {
   ArrayResize(b, 0, 4096);
   int n = 0;
   for(int j = 0; j < NB; j++)
     {
      datetime s = b_ny[j] + 7 * 3600;
      long key = (long)(s / len);
      if(n == 0 || b[n - 1].key != key)
        {
         ArrayResize(b, n + 1, 4096);
         b[n].key = key;
         b[n].close_utc = b_utc[j] + (datetime)(key * len + len - (long)s);
         b[n].h = b_h[j]; b[n].l = b_l[j];
         n++;
        }
      b[n - 1].h = MathMax(b[n - 1].h, b_h[j]);
      b[n - 1].l = MathMin(b[n - 1].l, b_l[j]);
      b[n - 1].c = b_c[j];
     }
   Wilder(b);
  }

double AtrAt(Bkt &b[], const datetime utc)  // the last bar closed by ``utc``; -1: none
  {
   for(int k = ArraySize(b) - 1; k >= 0; k--)
      if(b[k].close_utc <= utc)
         return k >= 50 ? b[k].atr : -1.0;
   return -1.0;
  }

bool Refresh()
  {
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M5, 1, Bars5m, r);  // closed bars, oldest first
   if(n < 2000)
      return false;
   NB = n;
   ArrayResize(b_srv, n); ArrayResize(b_utc, n); ArrayResize(b_ny, n);
   ArrayResize(b_o, n); ArrayResize(b_h, n); ArrayResize(b_l, n); ArrayResize(b_c, n);
   ArrayResize(atr5, n); ArrayResize(swl, n); ArrayResize(swh, n);
   for(int j = 0; j < n; j++)
     {
      b_srv[j] = r[j].time;
      b_utc[j] = ServerToUtc(r[j].time);
      b_ny[j]  = UtcToNy(b_utc[j]);
      b_o[j] = r[j].open; b_h[j] = r[j].high; b_l[j] = r[j].low; b_c[j] = r[j].close;
      double tr = b_h[j] - b_l[j];
      if(j > 0)
         tr = MathMax(tr, MathMax(MathAbs(b_h[j] - b_c[j - 1]), MathAbs(b_l[j] - b_c[j - 1])));
      atr5[j] = j == 0 ? tr : atr5[j - 1] + (tr - atr5[j - 1]) / 14.0;
      // the last swing low (high) confirmed by bar j: bar j-2 is the extreme of j-4 .. j
      swl[j] = j > 0 ? swl[j - 1] : -1.0;
      swh[j] = j > 0 ? swh[j - 1] : -1.0;
      if(j >= 4)
        {
         double mn = b_l[j - 4], mx = b_h[j - 4];
         for(int q = j - 3; q <= j; q++) { mn = MathMin(mn, b_l[q]); mx = MathMax(mx, b_h[q]); }
         if(b_l[j - 2] == mn) swl[j] = b_l[j - 2];
         if(b_h[j - 2] == mx) swh[j] = b_h[j - 2];
        }
     }
   Buckets(H1, 3600);
   Buckets(H4, 4 * 3600);
   ArrayResize(D1, 0, 512);
   int d = 0;
   for(int j = 0; j < n; j++)
     {
      long key = DayKey(b_ny[j]);
      if(d == 0 || D1[d - 1].key != key)
        {
         ArrayResize(D1, d + 1, 512);
         D1[d].key = key; D1[d].h = b_h[j]; D1[d].l = b_l[j];
         d++;
        }
      D1[d - 1].h = MathMax(D1[d - 1].h, b_h[j]);
      D1[d - 1].l = MathMin(D1[d - 1].l, b_l[j]);
      D1[d - 1].c = b_c[j];
     }
   return d >= 7 && ArraySize(H4) > 60;
  }

double SpreadMean(const datetime srv_open)  // mean M1 spread of a 5m bar, in price
  {
   MqlRates m[];
   int n = CopyRates(_Symbol, PERIOD_M1, srv_open, srv_open + 4 * 60, m);
   if(n <= 0)
      return -1.0;
   double s = 0.0;
   for(int k = 0; k < n; k++)
      s += m[k].spread;
   return s / n * _Point;
  }

// The levels of trading day ``key`` from the days before it; false when there are too few.
bool Levels(const long key, double &lv[][NK])
  {
   int last = ArraySize(D1) - 1;
   int p = D1[last].key == key ? last - 1 : last;  // the previous trading day
   if(p < 4)
      return false;
   lv[0][0] = D1[p].h;
   lv[0][1] = D1[p].l;
   lv[0][2] = D1[p].h; lv[0][3] = D1[p].l;
   for(int q = p - 4; q < p; q++) { lv[0][2] = MathMax(lv[0][2], D1[q].h); lv[0][3] = MathMin(lv[0][3], D1[q].l); }
   double pp = (D1[p].h + D1[p].l + D1[p].c) / 3.0;
   lv[1][0] = 2 * pp - D1[p].l;
   lv[1][1] = 2 * pp - D1[p].h;
   lv[2][0] = lv[1][0];
   lv[2][1] = lv[1][1];
   // ASIA: the range of this trading day's bars from 19:00 to 02:00 New York (0: none yet)
   lv[3][0] = 0.0; lv[3][1] = 0.0;
   for(int j = NB - 1; j >= 0 && DayKey(b_ny[j]) >= key; j--)
     {
      int m = NyMin(b_ny[j]);
      if(DayKey(b_ny[j]) != key || (m < 19 * 60 && m >= 120))
         continue;
      lv[3][0] = lv[3][0] == 0.0 ? b_h[j] : MathMax(lv[3][0], b_h[j]);
      lv[3][1] = lv[3][1] == 0.0 ? b_l[j] : MathMin(lv[3][1], b_l[j]);
     }
   // PWHL: the last week (Monday to Sunday, by the trading day's date) before this one with days
   long wk = Week(key), pw = -1;
   lv[4][0] = 0.0; lv[4][1] = 0.0;
   for(int q = last; q >= 0; q--)
     {
      long w = Week(D1[q].key);
      if(w >= wk)
         continue;
      if(pw < 0)
         pw = w;
      if(w != pw)
         break;
      lv[4][0] = lv[4][0] == 0.0 ? D1[q].h : MathMax(lv[4][0], D1[q].h);
      lv[4][1] = lv[4][1] == 0.0 ? D1[q].l : MathMin(lv[4][1], D1[q].l);
     }
   return true;
  }

bool InWindow(const datetime ny)
  {
   int dow = NyDow(ny), m = NyMin(ny);
   return dow >= 1 && dow <= 5 && m >= WIN_FROM && m < WIN_TO;
  }

double Dist(const int s, const datetime utc)  // PIVOT: ATR(1h); the others: LVL4H's 0.75 x ATR(4h)
  {
   double a = s == 1 ? AtrAt(H1, utc) : AtrAt(H4, utc);
   return a > 0 ? (s == 1 ? a : LVL_MULT * a) : -1.0;
  }

bool Enabled(const int s)
  {
   bool on[NS];
   on[0] = TradeLVL4H; on[1] = TradePIVOT; on[2] = TradePIVW; on[3] = TradeASIA; on[4] = TradePWHL;
   return on[s];
  }

// --- log ---------------------------------------------------------------------------------------

void Log(const string event, const int s, const string kind, const int dir, const datetime bar,
         const double level, const double e, const double sl, const double risk, const double lots,
         const ulong ticket, const double price, const string note)
  {
   int h = FileOpen(LogFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0)
      FileWriteString(h, "time_server,event,strategy,kind,dir,bar_server,level,entry,sl,risk,lots,ticket,price,note\r\n");
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, StringFormat("%s,%s,%s,%s,%d,%s,%s,%s,%s,%s,%.2f,%s,%s,%s\r\n",
                   TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), event, s >= 0 ? SNAME[s] : "", kind,
                   dir, bar > 0 ? TimeToString(bar, TIME_DATE | TIME_SECONDS) : "", DoubleToString(level, _Digits),
                   DoubleToString(e, _Digits), DoubleToString(sl, _Digits), DoubleToString(risk, _Digits), lots,
                   IntegerToString((long)ticket), DoubleToString(price, _Digits), note));
   FileClose(h);
  }

// --- trade state (terminal global variables, by the opening order's ticket) --------------------

string GV(const ulong id, const string f) { return "GL." + IntegerToString((long)id) + "." + f; }
double Get(const ulong id, const string f) { return GlobalVariableCheck(GV(id, f)) ? GlobalVariableGet(GV(id, f)) : 0.0; }
void   Set(const ulong id, const string f, const double v) { GlobalVariableSet(GV(id, f), v); }
void   Drop(const ulong id) { GlobalVariablesDeleteAll("GL." + IntegerToString((long)id) + "."); }

int Strat(const long magic) { long s = magic - MagicBase; return s >= 0 && s < NS ? (int)s : -1; }

bool HasPosition(const int s)
  {
   for(int k = PositionsTotal() - 1; k >= 0; k--)
      if(PositionGetTicket(k) > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol
         && Strat(PositionGetInteger(POSITION_MAGIC)) == s)
         return true;
   return false;
  }

void DeleteOrders(const int s)  // -1: every strategy
  {
   for(int k = OrdersTotal() - 1; k >= 0; k--)
     {
      ulong t = OrderGetTicket(k);
      if(t == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;
      int os = Strat(OrderGetInteger(ORDER_MAGIC));
      if(os < 0 || (s >= 0 && os != s))
         continue;
      if(trade.OrderDelete(t))
         Drop(t);
     }
  }

// --- signals -----------------------------------------------------------------------------------

int    why_dir[NS][NK];      // this bar: the direction placed (0: none)
string why_not[NS][NK];      // this bar: why no order ("" when placed)
double why_lv[NS][NK];
long   placed_day = 0, asia_day = 0;
bool   filled_today[NS][NK];

// Each kind's first touch of the day inside the window, over the closed bars of that day.
void Touched(const long key, double &lv[][NK], bool &done[][NK], int &last_touch[][NK])
  {
   for(int s = 0; s < NS; s++)
      for(int k = 0; k < NK; k++) { done[s][k] = false; last_touch[s][k] = -1; }
   int j0 = NB - 1;
   while(j0 > 0 && DayKey(b_ny[j0 - 1]) == key)
      j0--;
   if(DayKey(b_ny[NB - 1]) != key)
      return;
   for(int j = MathMax(j0, 1); j < NB; j++)
     {
      if(!InWindow(b_ny[j]))
         continue;
      for(int s = 0; s < NS; s++)
        {
         if(Dist(s, b_utc[j] + 300) <= 0)
            continue;
         for(int k = 0; k < NKINDS[s]; k++)
           {
            double v = lv[s][k];
            if(v <= 0)
               continue;
            bool t = (b_c[j - 1] < v && b_h[j] >= v) || (b_c[j - 1] > v && b_l[j] <= v);
            if(t && !done[s][k]) { done[s][k] = true; last_touch[s][k] = j; }
           }
        }
     }
  }

double Lots(const int s, const double risk)
  {
   if(FixedLots > 0)
      return FixedLots;
   double money = AccountInfoDouble(ACCOUNT_EQUITY) * (s >= 2 ? ShadowRiskPct : RiskPct) / 100.0;
   double per_lot = risk * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lots = MathFloor(money / per_lot / step) * step;
   return MathMin(lots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
  }

// The money the EA's open trades (to their current SL) and pending orders would lose. A strategy
// fills one of its orders (the others are then deleted), so its largest order counts; ``pend``
// is that of strategy ``s``.
double OpenRisk(const int s, double &pend)
  {
   double cs = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE), sum = 0.0;
   double most[NS];
   ArrayInitialize(most, 0.0);
   for(int q = PositionsTotal() - 1; q >= 0; q--)
     {
      if(PositionGetTicket(q) == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol
         || Strat(PositionGetInteger(POSITION_MAGIC)) < 0)
         continue;
      ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      double sl = Get(id, "sl") > 0 ? Get(id, "sl") : PositionGetDouble(POSITION_SL);
      int dir = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double r = sl > 0 ? dir * (PositionGetDouble(POSITION_PRICE_OPEN) - sl) : Get(id, "risk");
      if(r > 0)
         sum += r * PositionGetDouble(POSITION_VOLUME) * cs;
     }
   for(int k = OrdersTotal() - 1; k >= 0; k--)
     {
      int os = OrderGetTicket(k) == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol
               ? -1 : Strat(OrderGetInteger(ORDER_MAGIC));
      if(os < 0)
         continue;
      most[os] = MathMax(most[os], MathAbs(OrderGetDouble(ORDER_PRICE_OPEN) - OrderGetDouble(ORDER_SL))
                                   * OrderGetDouble(ORDER_VOLUME_CURRENT) * cs);
     }
   for(int q = 0; q < NS; q++)
      sum += most[q];
   pend = most[s];
   return sum;
  }

void Place(const int s, const int k, const int dir, const double lv, const double risk, const datetime bar)
  {
   string kind = KNAME[s][k];
   if(SignalsOnly)
     {
      why_not[s][k] = "signals only";  // a touch is logged at the next bar
      return;
     }
   MqlTick t;
   SymbolInfoTick(_Symbol, t);
   double gap = (double)MathMax(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
                                SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   bool through = dir > 0 ? t.ask >= lv - gap : t.bid <= lv + gap;
   double e = through ? (dir > 0 ? MathMax(lv, t.bid) : MathMin(lv, t.bid)) : lv;
   double sl = NormalizeDouble(e - dir * risk, _Digits);
   double lots = Lots(s, risk);
   if(lots < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
     {
      why_not[s][k] = "size";
      Log("SKIP", s, kind, dir, bar, lv, e, sl, risk, lots, 0, 0.0, "size below the minimum");
      return;
     }
   double add = risk * lots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double cap = AccountInfoDouble(ACCOUNT_EQUITY) * MaxOpenRiskPct / 100.0;
   double pend = 0.0;
   double open = OpenRisk(s, pend);
   if(MaxOpenRiskPct > 0 && open + MathMax(add - pend, 0.0) > cap)
     {
      why_not[s][k] = "risk cap";
      Log("SKIP", s, kind, dir, bar, lv, e, sl, risk, lots, 0, 0.0,
          StringFormat("open risk %.2f + %.2f over the cap %.2f", open, add, cap));
      return;
     }
   trade.SetExpertMagicNumber(MagicBase + s);
   string c = SNAME[s] + " " + kind;
   bool ok;
   if(!through)
      ok = dir > 0 ? trade.BuyStop(lots, lv, _Symbol, sl, 0.0, ORDER_TIME_SPECIFIED, bar + 300, c)
                   : trade.SellStop(lots, lv, _Symbol, sl, 0.0, ORDER_TIME_SPECIFIED, bar + 300, c);
   else
      ok = dir > 0 ? trade.Buy(lots, _Symbol, 0.0, sl, 0.0, c) : trade.Sell(lots, _Symbol, 0.0, sl, 0.0, c);
   uint rc = trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
     {
      why_not[s][k] = "retcode";
      Log("FAILED", s, kind, dir, bar, lv, e, sl, risk, lots, 0, 0.0, "retcode " + IntegerToString(rc));
      return;
     }
   ulong id = trade.ResultOrder();
   Set(id, "e", e); Set(id, "risk", risk); Set(id, "sl", sl); Set(id, "bar", (double)bar);
   Set(id, "dir", dir); Set(id, "kind", k); Set(id, "lv", lv); Set(id, "market", through ? 1 : 0);
   why_dir[s][k] = dir;
  }

void Signals(const datetime bar)
  {
   datetime utc = ServerToUtc(bar), ny = UtcToNy(utc);
   long key = DayKey(ny);
   double lv[NS][NK];
   bool done[NS][NK];
   int last_touch[NS][NK];
   if(!Levels(key, lv))
      return;
   if(key != placed_day)
     {
      placed_day = key;
      for(int s = 0; s < NS; s++) for(int k = 0; k < NK; k++) filled_today[s][k] = false;
      Log("DAY", -1, "", 0, bar, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0,
          StringFormat("PDH %.2f; PDL %.2f; 5DH %.2f; 5DL %.2f; R1 %.2f; S1 %.2f; PWH %.2f; PWL %.2f",
                       lv[0][0], lv[0][1], lv[0][2], lv[0][3], lv[1][0], lv[1][1], lv[4][0], lv[4][1]));
     }
   if(key != asia_day && InWindow(ny))
     {
      asia_day = key;
      Log("ASIA", -1, "", 0, bar, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0,
          StringFormat("ASH %.2f; ASL %.2f", lv[3][0], lv[3][1]));
     }
   Touched(key, lv, done, last_touch);
   // the previous bar: a touch that did not fill, and why
   for(int s = 0; s < NS; s++)
      for(int k = 0; k < NKINDS[s]; k++)
        {
         if(last_touch[s][k] == NB - 1 && !filled_today[s][k] && b_srv[NB - 1] == bar - 300)
            Log("TOUCH", s, KNAME[s][k], b_c[NB - 2] < lv[s][k] ? 1 : -1, b_srv[NB - 1], lv[s][k], 0.0, 0.0,
                Dist(s, b_utc[NB - 1] + 300), 0.0, 0, 0.0, why_not[s][k] == "" ? "no fill" : why_not[s][k]);
         why_dir[s][k] = 0;
         why_not[s][k] = "";
        }
   if(!InWindow(ny))
      return;
   for(int s = 0; s < NS; s++)
     {
      if(!Enabled(s))
         continue;
      bool busy = !SignalsOnly && HasPosition(s);
      double risk = Dist(s, utc);
      double spread = SpreadMean(b_srv[NB - 1]);
      double prices[];
      int dirs[];
      for(int k = 0; k < NKINDS[s]; k++)
        {
         if(done[s][k])
            continue;
         double v = lv[s][k];
         if(v <= 0)
            continue;
         int dir = b_c[NB - 1] < v ? 1 : (b_c[NB - 1] > v ? -1 : 0);
         if(dir == 0)
            continue;
         if(busy) { why_not[s][k] = "busy"; continue; }
         if(risk <= 0) { why_not[s][k] = "no ATR"; continue; }
         if(s != 1 && (spread < 0 || (spread + COMMISSION) / risk > LVL_CAP)) { why_not[s][k] = "cost cap"; continue; }
         bool dup = false;  // one order per price and direction (5DH is often PDH)
         for(int q = 0; q < ArraySize(prices); q++)
            if(dirs[q] == dir && MathAbs(prices[q] - v) < _Point / 2) dup = true;
         if(dup) { why_not[s][k] = "same level"; continue; }
         int m = ArraySize(prices);
         ArrayResize(prices, m + 1); ArrayResize(dirs, m + 1);
         prices[m] = v; dirs[m] = dir;
         Place(s, k, dir, NormalizeDouble(v, _Digits), risk, bar);
        }
     }
  }

// --- management --------------------------------------------------------------------------------

int BarIndex(const datetime srv)  // the closed bar that opened at ``srv``; -1: none
  {
   for(int j = NB - 1; j >= 0 && b_srv[j] >= srv; j--)
      if(b_srv[j] == srv)
         return j;
   return -1;
  }

void Close(const ulong ticket, const ulong id, const int s, const string why)
  {
   string kind = KNAME[s][(int)Get(id, "kind")];  // read before the close drops the state
   int dir = (int)Get(id, "dir");
   datetime bar = (datetime)Get(id, "bar");
   double e = Get(id, "e"), risk = Get(id, "risk"), lv = Get(id, "lv");
   if(trade.PositionClose(ticket))
      Log("EXIT", s, kind, dir, bar, lv, e, 0.0, risk, 0.0, id, trade.ResultPrice(), why);
  }

// M8 with the bar just closed, and the horizon, for every open trade.
void Manage()
  {
   int j = NB - 1;
   for(int q = PositionsTotal() - 1; q >= 0; q--)
     {
      ulong ticket = PositionGetTicket(q);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      int s = Strat(PositionGetInteger(POSITION_MAGIC));
      ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(s < 0 || !GlobalVariableCheck(GV(id, "e")))
         continue;
      datetime bar = (datetime)Get(id, "bar");
      int i = BarIndex(bar);
      if(i < 0 || j <= i)
         continue;  // the entry bar itself is not managed (as the backtest)
      if(j - i >= HORIZON[s])
        {
         Close(ticket, id, s, "horizon");
         continue;
        }
      int dir = (int)Get(id, "dir");
      double e = Get(id, "e"), risk = Get(id, "risk");
      double sl = Get(id, "watched") > 0 ? Get(id, "watched") : Get(id, "sl");
      double old = sl;
      if(Get(id, "cost") <= 0)
        {
         double sp = SpreadMean(bar);
         Set(id, "cost", (sp > 0 ? sp : 0.0) + COMMISSION);
        }
      double cost = Get(id, "cost");
      double best = dir > 0 ? b_h[j] - e : e - b_l[j];
      if(Get(id, "armed") == 0 && best >= risk)
        {
         Set(id, "armed", 1);
         double be = e + dir * cost;
         if(dir * (be - sl) > 0)
            sl = be;
        }
      if(Get(id, "armed") != 0)
        {
         double sw = dir > 0 ? (swl[j] > 0 ? swl[j] - 0.1 * atr5[j] : -1.0) : (swh[j] > 0 ? swh[j] + 0.1 * atr5[j] : -1.0);
         if(sw > 0 && dir * (sw - sl) > 0 && dir * (b_c[j] - sw) > 0)
            sl = sw;
        }
      if(sl == old)
        continue;
      sl = NormalizeDouble(sl, _Digits);
      Set(id, "sl", sl);
      if(trade.PositionModify(ticket, sl, 0.0))
        {
         Set(id, "watched", 0.0);
         Log("SL", s, KNAME[s][(int)Get(id, "kind")], dir, b_srv[j], 0.0, e, sl, risk, 0.0, id, 0.0, "");
        }
      else
        {
         Set(id, "watched", sl);  // inside the stops level: the EA watches it (the broker's SL stays)
         Log("SL", s, KNAME[s][(int)Get(id, "kind")], dir, b_srv[j], 0.0, e, sl, risk, 0.0, id, 0.0,
             "watched; retcode " + IntegerToString(trade.ResultRetcode()));
        }
     }
  }

// Every tick: fills, the other orders of a filled strategy, the watched SL, 16:45 New York.
void Watch()
  {
   MqlTick t;
   SymbolInfoTick(_Symbol, t);
   datetime ny = UtcToNy(ServerToUtc(t.time));
   for(int q = PositionsTotal() - 1; q >= 0; q--)
     {
      ulong ticket = PositionGetTicket(q);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      int s = Strat(PositionGetInteger(POSITION_MAGIC));
      ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(s < 0 || !GlobalVariableCheck(GV(id, "e")))
         continue;
      int k = (int)Get(id, "kind");
      if(Get(id, "filled") == 0)
        {
         Set(id, "filled", 1);
         filled_today[s][k] = true;
         DeleteOrders(s);
         Log("FILL", s, KNAME[s][k], (int)Get(id, "dir"), (datetime)Get(id, "bar"), Get(id, "lv"), Get(id, "e"),
             PositionGetDouble(POSITION_SL), Get(id, "risk"), PositionGetDouble(POSITION_VOLUME), id,
             PositionGetDouble(POSITION_PRICE_OPEN), Get(id, "market") != 0 ? "market" : "stop");
        }
      int dir = (int)Get(id, "dir");
      double w = Get(id, "watched");
      if(w > 0 && (dir > 0 ? t.bid <= w : t.ask >= w))
        {
         Close(ticket, id, s, "sl watched");
         continue;
        }
      datetime bar_ny = UtcToNy(ServerToUtc((datetime)Get(id, "bar")));
      if(CalDay(ny) > CalDay(bar_ny) || NyMin(ny) >= END_MIN)
         Close(ticket, id, s, "16:45");
     }
  }

void OnTradeTransaction(const MqlTradeTransaction &tx, const MqlTradeRequest &rq, const MqlTradeResult &rs)
  {
   if(tx.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(tx.deal))
      return;
   if(HistoryDealGetInteger(tx.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT)
      return;
   int s = Strat(HistoryDealGetInteger(tx.deal, DEAL_MAGIC));
   ulong id = (ulong)HistoryDealGetInteger(tx.deal, DEAL_POSITION_ID);
   if(s < 0 || !GlobalVariableCheck(GV(id, "e")))
      return;
   if(HistoryDealGetInteger(tx.deal, DEAL_REASON) == DEAL_REASON_SL)
      Log("EXIT", s, KNAME[s][(int)Get(id, "kind")], (int)Get(id, "dir"), (datetime)Get(id, "bar"), Get(id, "lv"),
          Get(id, "e"), 0.0, Get(id, "risk"), 0.0, id, HistoryDealGetDouble(tx.deal, DEAL_PRICE), "sl");
   Log("DEAL", s, "", 0, 0, 0.0, 0.0, 0.0, 0.0, HistoryDealGetDouble(tx.deal, DEAL_VOLUME), id,
       HistoryDealGetDouble(tx.deal, DEAL_PROFIT) + HistoryDealGetDouble(tx.deal, DEAL_COMMISSION)
       + HistoryDealGetDouble(tx.deal, DEAL_SWAP) + HistoryDealGetDouble(tx.deal, DEAL_FEE), "net money");
   Drop(id);
  }

int OnInit()
  {
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("GoldLive needs a hedging account: its strategies may hold opposite trades");
      return INIT_FAILED;
     }
   if(StringFind(_Symbol, "GOLD") != 0 && StringFind(_Symbol, "XAUUSD") != 0)
     {
      PrintFormat("GoldLive runs on gold, not %s", _Symbol);
      return INIT_FAILED;
     }
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   for(int s = 0; s < NS; s++) for(int k = 0; k < NK; k++) { why_dir[s][k] = 0; why_not[s][k] = ""; filled_today[s][k] = false; }
   Log("START", -1, "", 0, 0, 0.0, 0.0, 0.0, 0.0, FixedLots, 0, RiskPct,
       StringFormat("v1 risk %.2f%%; shadow %.2f%%; open risk cap %.2f%%; signals only %s",
                    RiskPct, ShadowRiskPct, MaxOpenRiskPct, SignalsOnly ? "yes" : "no"));
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   datetime bar = iTime(_Symbol, PERIOD_M5, 0);
   if(bar != last_bar && bar > 0)
     {
      if(!Refresh())
         return;  // history still loading: try again on the next tick
      last_bar = bar;
      DeleteOrders(-1);  // orders were valid for the bar that just closed
      Manage();
      Signals(bar);
     }
   Watch();
  }
