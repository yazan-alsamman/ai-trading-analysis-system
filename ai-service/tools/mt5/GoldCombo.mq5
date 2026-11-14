//+------------------------------------------------------------------+
//| GoldCombo.mq5: replays the gold combination of the commercial     |
//| track (ai-service/app/research/gold_combo.py) in the MT5 Strategy |
//| Tester, on real ticks, with the M8 SL moves.                      |
//|                                                                   |
//| Expert Advisor, Strategy Tester only, on GOLD, "Every tick based  |
//| on real ticks", a hedging account.                                |
//| Reads  <Common>/Files/gold_combo_trades.csv                       |
//|        (python -m app research gold-combo build)                  |
//| Writes <Common>/Files/gold_combo_replay[_<Part>].csv              |
//|                                                                   |
//| Each trade: a stop order at the level at the open of the touch    |
//| bar, valid to its close (at market when price is already at or    |
//| through it), with the SL and no TP (M8). At each listed time the  |
//| SL moves to the listed price (break-even, then the structure      |
//| trail); a move the broker refuses is watched by the EA. Closed at |
//| market at the exit time. UseAI: only the trades the AI filter     |
//| keeps. Results are read in R.                                     |
//+------------------------------------------------------------------+
#include <Trade\Trade.mqh>

input string TradesFile = "gold_combo_trades.csv";  // in <Common>/Files
input bool   UseAI      = true;                      // only the trades the AI filter keeps
input double Lots       = 1.0;
input string Part       = "";                        // a run over part of the period: its own file

enum RowState { WAITING, PENDING, OPEN, CLOSED, EXPIRED, FAILED, SKIPPED };

struct Row
  {
   long              id;
   string            strategy;
   int               dir;
   datetime          place_time, expire_time, exit_time;
   double            level, sl;
   int               first_move;    // its SL moves are mv_time / mv_sl [first_move, end_move)
   int               end_move;
   int               next_move;
   double            watched;       // an SL the EA watches (0: none)
   RowState          state;
   ulong             ticket;
   string            fill, note, close_reason;
   double            risk_money;
   datetime          open_time, close_time;
   double            open_price, close_price, profit, commission, fee, swap;
  };

Row      rows[];
datetime mv_time[];
double   mv_sl[];
int    next_row = 0;
int    active[];
CTrade trade;

bool Load()
  {
   int h = FileOpen(TradesFile, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("cannot open <Common>/Files/%s: error %d", TradesFile, GetLastError());
      return false;
     }
   FileReadString(h);  // id,strategy,dir,place_server,expire_server,exit_server,entry,sl,moves,take
   int n = 0;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      StringTrimRight(line);
      string f[];
      if(StringSplit(line, ',', f) < 10)
         continue;
      ArrayResize(rows, n + 1, 4096);
      rows[n].id          = StringToInteger(f[0]);
      rows[n].strategy    = f[1];
      rows[n].dir         = f[2] == "buy" ? 1 : -1;
      rows[n].place_time  = StringToTime(f[3]);
      rows[n].expire_time = StringToTime(f[4]);
      rows[n].exit_time   = StringToTime(f[5]);
      rows[n].level       = NormalizeDouble(StringToDouble(f[6]), _Digits);
      rows[n].sl          = NormalizeDouble(StringToDouble(f[7]), _Digits);
      rows[n].state       = (UseAI && StringToInteger(f[9]) == 0) ? SKIPPED : WAITING;
      rows[n].watched     = 0.0;
      rows[n].fill = ""; rows[n].note = ""; rows[n].close_reason = "";
      string mv[];
      int k = StringLen(f[8]) > 0 ? StringSplit(f[8], ';', mv) : 0;
      int base = ArraySize(mv_time);
      ArrayResize(mv_time, base + k, 65536);
      ArrayResize(mv_sl, base + k, 65536);
      for(int m = 0; m < k; m++)
        {
         string p[];
         StringSplit(mv[m], '@', p);
         mv_time[base + m] = StringToTime(p[0]);
         mv_sl[base + m]   = NormalizeDouble(StringToDouble(p[1]), _Digits);
        }
      rows[n].first_move = base;
      rows[n].end_move   = base + k;
      rows[n].next_move  = base;
      n++;
     }
   FileClose(h);
   return n > 0;
  }

int OnInit()
  {
   if(!MQLInfoInteger(MQL_TESTER))
     {
      Print("GoldCombo runs in the Strategy Tester only");
      return INIT_FAILED;
     }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("GoldCombo needs a hedging account: trades overlap");
      return INIT_FAILED;
     }
   if(StringFind(_Symbol, "GOLD") != 0 && StringFind(_Symbol, "XAUUSD") != 0)
     {
      PrintFormat("GoldCombo runs on gold, not %s", _Symbol);
      return INIT_FAILED;
     }
   if(!Load())
      return INIT_FAILED;
   trade.SetExpertMagicNumber(20261105);
   trade.SetDeviationInPoints(100000);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   PrintFormat("GoldCombo: %d trades (UseAI %s), first %s, last %s", ArraySize(rows), UseAI ? "on" : "off",
               TimeToString(rows[0].place_time), TimeToString(rows[ArraySize(rows) - 1].place_time));
   return INIT_SUCCEEDED;
  }

void Activate(const int i)
  {
   int n = ArraySize(active);
   ArrayResize(active, n + 1, 256);
   active[n] = i;
  }

void Place(const int i)
  {
   MqlTick t;
   SymbolInfoTick(_Symbol, t);
   double pl = 0.0;
   ENUM_ORDER_TYPE market = rows[i].dir > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   rows[i].risk_money = OrderCalcProfit(market, _Symbol, Lots, rows[i].level, rows[i].sl, pl) ? MathAbs(pl) : 0.0;
   string c = IntegerToString(rows[i].id);
   long lvl = MathMax(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL));
   double gap = (double)lvl * _Point;
   bool through = rows[i].dir > 0 ? t.ask >= rows[i].level - gap : t.bid <= rows[i].level + gap;
   bool ok = false;
   if(!through)
     {
      rows[i].fill = "stop";
      ok = rows[i].dir > 0
           ? trade.BuyStop(Lots, rows[i].level, _Symbol, rows[i].sl, 0.0, ORDER_TIME_SPECIFIED, rows[i].expire_time, c)
           : trade.SellStop(Lots, rows[i].level, _Symbol, rows[i].sl, 0.0, ORDER_TIME_SPECIFIED, rows[i].expire_time, c);
      through = !ok && trade.ResultRetcode() == TRADE_RETCODE_INVALID_PRICE;
     }
   if(through)
     {
      rows[i].fill = "market";
      ok = rows[i].dir > 0 ? trade.Buy(Lots, _Symbol, 0.0, rows[i].sl, 0.0, c) : trade.Sell(Lots, _Symbol, 0.0, rows[i].sl, 0.0, c);
      if(!ok && trade.ResultRetcode() == TRADE_RETCODE_INVALID_STOPS)
        {
         rows[i].watched = rows[i].sl;  // the SL is inside the stops level: the EA watches it
         ok = rows[i].dir > 0 ? trade.Buy(Lots, _Symbol, 0.0, 0.0, 0.0, c) : trade.Sell(Lots, _Symbol, 0.0, 0.0, 0.0, c);
        }
     }
   uint rc = trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
     {
      rows[i].state = FAILED;
      rows[i].note  = "retcode " + IntegerToString(rc);
      return;
     }
   rows[i].ticket = trade.ResultOrder();
   rows[i].state  = PENDING;
   Activate(i);
  }

bool Collect(const int i)
  {
   rows[i].profit = rows[i].commission = rows[i].fee = rows[i].swap = 0.0;
   if(!HistorySelectByPosition(rows[i].ticket) || HistoryDealsTotal() == 0)
      return false;
   for(int k = 0; k < HistoryDealsTotal(); k++)
     {
      ulong d = HistoryDealGetTicket(k);
      rows[i].commission += HistoryDealGetDouble(d, DEAL_COMMISSION);
      rows[i].fee        += HistoryDealGetDouble(d, DEAL_FEE);
      rows[i].swap       += HistoryDealGetDouble(d, DEAL_SWAP);
      rows[i].profit     += HistoryDealGetDouble(d, DEAL_PROFIT);
      ENUM_DEAL_ENTRY e = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e == DEAL_ENTRY_IN)
        {
         rows[i].open_time  = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         rows[i].open_price = HistoryDealGetDouble(d, DEAL_PRICE);
        }
      if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY)
        {
         rows[i].close_time  = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         rows[i].close_price = HistoryDealGetDouble(d, DEAL_PRICE);
         ENUM_DEAL_REASON r  = (ENUM_DEAL_REASON)HistoryDealGetInteger(d, DEAL_REASON);
         if(rows[i].close_reason == "")
            rows[i].close_reason = r == DEAL_REASON_SL ? "sl" : r == DEAL_REASON_EXPERT ? "time" : EnumToString(r);
        }
     }
   return true;
  }

// The SL moves whose time has come; a move the broker refuses is watched by the EA.
void Moves(const int i, const datetime now)
  {
   while(rows[i].next_move < rows[i].end_move && mv_time[rows[i].next_move] <= now)
     {
      double sl = mv_sl[rows[i].next_move++];
      if(rows[i].watched == 0.0 && trade.PositionModify(rows[i].ticket, sl, 0.0))
         continue;
      if(rows[i].watched == 0.0)                         // refused: the EA watches the SL from now on
         trade.PositionModify(rows[i].ticket, 0.0, 0.0);
      rows[i].watched = sl;                              // already watched: only the level moves
     }
  }

bool WatchedHit(const int i)
  {
   if(rows[i].watched == 0.0)
      return false;
   MqlTick t;
   SymbolInfoTick(_Symbol, t);
   return rows[i].dir > 0 ? t.bid <= rows[i].watched : t.ask >= rows[i].watched;
  }

void OnTick()
  {
   datetime now = TimeCurrent();
   int n = ArraySize(rows);
   while(next_row < n && rows[next_row].place_time <= now)
     {
      if(rows[next_row].state == WAITING)
        {
         if(now < rows[next_row].expire_time)
            Place(next_row);
         else
           {
            rows[next_row].state = EXPIRED;
            rows[next_row].note  = "no tick in the bar";
           }
        }
      next_row++;
     }
   for(int k = ArraySize(active) - 1; k >= 0; k--)
     {
      int i = active[k];
      bool done = false;
      if(rows[i].state == PENDING)
        {
         if(OrderSelect(rows[i].ticket))
           {
            if(now >= rows[i].expire_time && trade.OrderDelete(rows[i].ticket))
              {
               rows[i].state = EXPIRED;
               done = true;
              }
           }
         else if(PositionSelectByTicket(rows[i].ticket))
            rows[i].state = OPEN;
         else
           {
            rows[i].state = Collect(i) ? CLOSED : EXPIRED;
            done = true;
           }
        }
      if(rows[i].state == OPEN)
        {
         if(!PositionSelectByTicket(rows[i].ticket))
           {
            rows[i].state = Collect(i) ? CLOSED : FAILED;
            done = true;
           }
         else
           {
            Moves(i, now);
            bool hit = WatchedHit(i);
            if((hit || now >= rows[i].exit_time) && trade.PositionClose(rows[i].ticket))
              {
               if(hit)
                  rows[i].close_reason = "sl";
               rows[i].state = Collect(i) ? CLOSED : FAILED;
               done = true;
              }
           }
        }
      if(done)
         ArrayRemove(active, k, 1);
     }
  }

string Px(const double v) { return DoubleToString(v, _Digits); }
string Tm(const datetime t) { return t > 0 ? TimeToString(t, TIME_DATE | TIME_SECONDS) : ""; }

void OnDeinit(const int reason)
  {
   if(reason == REASON_INITFAILED || ArraySize(rows) == 0)
      return;
   string file = "gold_combo_replay" + (Part == "" ? "" : "_" + Part) + ".csv";
   int h = FileOpen(file, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("cannot write <Common>/Files/%s: error %d", file, GetLastError());
      return;
     }
   FileWriteString(h, "id,strategy,status,fill,note,open_time,open_price,close_time,close_price,close_reason,"
                      "profit,commission,fee,swap,risk_money\r\n");
   string names[7] = {"not_reached", "pending_at_end", "open_at_end", "closed", "expired", "failed", "skipped"};
   int counts[7] = {0, 0, 0, 0, 0, 0, 0};
   double total = 0.0;
   for(int i = 0; i < ArraySize(rows); i++)
     {
      counts[rows[i].state]++;
      if(rows[i].state == CLOSED && rows[i].risk_money > 0)
         total += (rows[i].profit + rows[i].commission + rows[i].fee + rows[i].swap) / rows[i].risk_money;
      FileWriteString(h, IntegerToString(rows[i].id) + "," + rows[i].strategy + "," + names[rows[i].state] + ","
                      + rows[i].fill + "," + rows[i].note + "," + Tm(rows[i].open_time) + "," + Px(rows[i].open_price) + ","
                      + Tm(rows[i].close_time) + "," + Px(rows[i].close_price) + "," + rows[i].close_reason + ","
                      + DoubleToString(rows[i].profit, 2) + "," + DoubleToString(rows[i].commission, 2) + ","
                      + DoubleToString(rows[i].fee, 2) + "," + DoubleToString(rows[i].swap, 2) + ","
                      + DoubleToString(rows[i].risk_money, 2) + "\r\n");
     }
   FileClose(h);
   PrintFormat("GoldCombo: closed %d, expired %d, failed %d, skipped %d, open at the end %d, not reached %d; "
               "mean net R of the closed trades %.4f; wrote <Common>/Files/%s",
               counts[CLOSED], counts[EXPIRED], counts[FAILED], counts[SKIPPED], counts[OPEN], counts[WAITING],
               counts[CLOSED] > 0 ? total / counts[CLOSED] : 0.0, file);
  }
//+------------------------------------------------------------------+
