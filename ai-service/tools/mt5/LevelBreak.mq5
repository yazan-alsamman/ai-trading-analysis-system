//+------------------------------------------------------------------+
//| LevelBreak.mq5: the Addendum 2 level-break trades (H_L2) in the   |
//| MT5 Strategy Tester (ai-service/app/research/levels_trade.py,     |
//| docs/strategies/ADDENDUM_2_LEVEL_BREAK.md, section 3).            |
//|                                                                   |
//| Expert Advisor, Strategy Tester only, one run per instrument,     |
//| "Every tick based on real ticks", a hedging account.              |
//| Reads  <Common>/Files/levels_trades.csv                           |
//|        (python -m app research levels-trade export)               |
//| Writes <Common>/Files/levels_replay_<ResearchName>.csv            |
//|        (read by python -m app research levels-trade compare)      |
//|                                                                   |
//| At the open of each touch bar it places a stop order at the level |
//| (buy stop from below, sell stop from above) with the SL and TP,   |
//| valid to the bar's close; if price is already through the level   |
//| it enters at market (marked "gap"). An open trade is closed at    |
//| market at its exit time. Results are read in R.                   |
//+------------------------------------------------------------------+
#include <Trade\Trade.mqh>

input string ResearchName = "NZDUSD";             // research name of the tested symbol
input string TradesFile   = "levels_trades.csv";  // in <Common>/Files
input double Lots         = 1.0;

enum RowState { WAITING, PENDING, OPEN, CLOSED, EXPIRED, FAILED };

struct Row
  {
   long              id;
   int               dir;
   datetime          place_time, expire_time, exit_time;
   double            level, sl, tp;
   RowState          state;
   ulong             ticket;        // the order ticket; the position id of the trade
   string            fill;          // "stop" or "gap"
   string            note;
   double            risk_money;
   datetime          open_time, close_time;
   double            open_price, close_price, profit, commission, fee, swap;
   string            close_reason;
  };

Row    rows[];
int    next_row = 0;
int    active[];
CTrade trade;

bool Matches()
  {
   if(StringFind(_Symbol, ResearchName) == 0)
      return true;
   return ResearchName == "XAGUSD" && StringFind(_Symbol, "SILVER") == 0;
  }

//--- id,symbol,kind,dir,place_server,expire_server,exit_server,level,sl,tp,d
bool Load()
  {
   int h = FileOpen(TradesFile, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("cannot open <Common>/Files/%s: error %d", TradesFile, GetLastError());
      return false;
     }
   FileReadString(h);
   int n = 0;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      StringTrimRight(line);
      string f[];
      if(StringSplit(line, ',', f) < 11 || f[1] != ResearchName)
         continue;
      ArrayResize(rows, n + 1, 8192);
      rows[n].id          = StringToInteger(f[0]);
      rows[n].dir         = f[3] == "buy" ? 1 : -1;
      rows[n].place_time  = StringToTime(f[4]);
      rows[n].expire_time = StringToTime(f[5]);
      rows[n].exit_time   = StringToTime(f[6]);
      rows[n].level       = NormalizeDouble(StringToDouble(f[7]), _Digits);
      rows[n].sl          = NormalizeDouble(StringToDouble(f[8]), _Digits);
      rows[n].tp          = NormalizeDouble(StringToDouble(f[9]), _Digits);
      rows[n].state       = WAITING;
      rows[n].fill        = "";
      rows[n].note        = "";
      n++;
     }
   FileClose(h);
   return n > 0;
  }

int OnInit()
  {
   if(!MQLInfoInteger(MQL_TESTER))
     {
      Print("LevelBreak runs in the Strategy Tester only");
      return INIT_FAILED;
     }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("LevelBreak needs a hedging account: trades overlap");
      return INIT_FAILED;
     }
   if(!Matches())
     {
      PrintFormat("ResearchName %s does not match the tested symbol %s: set it in Inputs", ResearchName, _Symbol);
      return INIT_FAILED;
     }
   if(!Load())
     {
      PrintFormat("no trade for %s in %s", ResearchName, TradesFile);
      return INIT_FAILED;
     }
   trade.SetExpertMagicNumber(20261104);
   trade.SetDeviationInPoints(100000);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   PrintFormat("%s: %d trades on %s, first %s, last %s", ResearchName, ArraySize(rows), _Symbol,
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
   ENUM_ORDER_TYPE market = rows[i].dir > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double pl = 0.0;
   rows[i].risk_money = OrderCalcProfit(market, _Symbol, Lots, rows[i].level, rows[i].sl, pl) ? MathAbs(pl) : 0.0;
   string c = IntegerToString(rows[i].id);
   bool through = rows[i].dir > 0 ? t.ask >= rows[i].level : t.bid <= rows[i].level;
   bool ok;
   if(through)
     {
      rows[i].fill = "gap";
      ok = rows[i].dir > 0 ? trade.Buy(Lots, _Symbol, 0.0, rows[i].sl, rows[i].tp, c)
                           : trade.Sell(Lots, _Symbol, 0.0, rows[i].sl, rows[i].tp, c);
     }
   else
     {
      rows[i].fill = "stop";
      ok = rows[i].dir > 0
           ? trade.BuyStop(Lots, rows[i].level, _Symbol, rows[i].sl, rows[i].tp, ORDER_TIME_SPECIFIED, rows[i].expire_time, c)
           : trade.SellStop(Lots, rows[i].level, _Symbol, rows[i].sl, rows[i].tp, ORDER_TIME_SPECIFIED, rows[i].expire_time, c);
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

// Fills the result from the position's deals; false when the order never filled.
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
         rows[i].close_reason = r == DEAL_REASON_SL ? "sl" : r == DEAL_REASON_TP ? "tp"
                              : r == DEAL_REASON_EXPERT ? "time" : EnumToString(r);
        }
     }
   return true;
  }

void OnTick()
  {
   datetime now = TimeCurrent();
   int n = ArraySize(rows);
   while(next_row < n && rows[next_row].place_time <= now)
     {
      if(now < rows[next_row].expire_time)
         Place(next_row);
      else
        {
         rows[next_row].state = EXPIRED;  // no tick inside the touch bar
         rows[next_row].note  = "no tick in the bar";
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
         else if(now >= rows[i].exit_time && trade.PositionClose(rows[i].ticket))
           {
            rows[i].state = Collect(i) ? CLOSED : FAILED;
            done = true;
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
      return;  // keep the file of an earlier good run
   string file = "levels_replay_" + ResearchName + ".csv";
   int h = FileOpen(file, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("cannot write <Common>/Files/%s: error %d", file, GetLastError());
      return;
     }
   FileWriteString(h, "id,status,fill,note,open_time,open_price,close_time,close_price,close_reason,"
                      "profit,commission,fee,swap,risk_money\r\n");
   string names[6] = {"not_reached", "pending_at_end", "open_at_end", "closed", "expired", "failed"};
   int counts[6] = {0, 0, 0, 0, 0, 0};
   for(int i = 0; i < ArraySize(rows); i++)
     {
      counts[rows[i].state]++;
      FileWriteString(h, IntegerToString(rows[i].id) + "," + names[rows[i].state] + "," + rows[i].fill + ","
                      + rows[i].note + "," + Tm(rows[i].open_time) + "," + Px(rows[i].open_price) + ","
                      + Tm(rows[i].close_time) + "," + Px(rows[i].close_price) + "," + rows[i].close_reason + ","
                      + DoubleToString(rows[i].profit, 2) + "," + DoubleToString(rows[i].commission, 2) + ","
                      + DoubleToString(rows[i].fee, 2) + "," + DoubleToString(rows[i].swap, 2) + ","
                      + DoubleToString(rows[i].risk_money, 2) + "\r\n");
     }
   FileClose(h);
   PrintFormat("%s: closed %d, expired %d, failed %d, open at the end %d, not reached %d; wrote <Common>/Files/%s",
               ResearchName, counts[CLOSED], counts[EXPIRED], counts[FAILED], counts[OPEN], counts[WAITING], file);
  }
//+------------------------------------------------------------------+
