//+------------------------------------------------------------------+
//| ReplayTrades.mq5: replays the research trades in the MT5          |
//| Strategy Tester to check the cost model                           |
//| (ai-service/app/research/mt5_check.py). Descriptive only.         |
//|                                                                   |
//| Expert Advisor, Strategy Tester only, one run per instrument,     |
//| "Every tick based on real ticks", a hedging account.              |
//| Reads  <Common>/Files/ai_replay_trades.csv                        |
//|        (python -m app research mt5-check export)                  |
//| Writes <Common>/Files/mt5_replay_<ResearchName>.csv               |
//|        (read by python -m app research mt5-check compare)         |
//|                                                                   |
//| Each trade opens at market on the first tick at or after its      |
//| entry time, with the research SL and TP levels, and is closed at  |
//| market at the research exit time if neither was hit. The lot size |
//| does not matter: results are read in R.                           |
//+------------------------------------------------------------------+
#include <Trade\Trade.mqh>

input string ResearchName = "XAUUSD";               // research name of the tested symbol
input string TradesFile   = "ai_replay_trades.csv"; // in <Common>/Files
input double Lots         = 1.0;                    // large enough that cents do not matter

enum RowState { WAITING, OPEN, CLOSED, FAILED };

struct Row
  {
   long              id;
   int               dir;           // +1 buy, -1 sell
   datetime          entry_time;    // server time
   datetime          exit_time;
   double            entry, sl, tp;
   RowState          state;
   ulong             position;
   string            note;
   datetime          open_time;
   double            open_bid, open_ask, open_price, m1_close, risk_money;
   datetime          close_time;
   double            close_price, profit, commission, fee, swap;
   string            close_reason;
  };

Row    rows[];
int    next_row = 0;
int    open_rows[];
CTrade trade;

//--- the research CSV: id,symbol,strategy,type,direction,entry_server,exit_server,entry,sl,tp,risk,k,reason
bool Load()
  {
   int h = FileOpen(TradesFile, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("cannot open <Common>/Files/%s: error %d", TradesFile, GetLastError());
      return false;
     }
   FileReadString(h);  // header
   int n = 0;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      StringTrimRight(line);
      string f[];
      if(StringSplit(line, ',', f) < 13 || f[1] != ResearchName)
         continue;
      ArrayResize(rows, n + 1, 4096);
      rows[n].id         = StringToInteger(f[0]);
      rows[n].dir        = f[4] == "buy" ? 1 : -1;
      rows[n].entry_time = StringToTime(f[5]);
      rows[n].exit_time  = StringToTime(f[6]);
      rows[n].entry      = StringToDouble(f[7]);
      rows[n].sl         = NormalizeDouble(StringToDouble(f[8]), _Digits);
      rows[n].tp         = NormalizeDouble(StringToDouble(f[9]), _Digits);
      rows[n].state      = WAITING;
      rows[n].note       = "";
      n++;
     }
   FileClose(h);
   return n > 0;
  }

int OnInit()
  {
   if(!MQLInfoInteger(MQL_TESTER))
     {
      Print("ReplayTrades runs in the Strategy Tester only");
      return INIT_FAILED;
     }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("ReplayTrades needs a hedging account: trades of different strategies overlap");
      return INIT_FAILED;
     }
   // GOLD is XAUUSD's name in the FxPro account; a suffix (EURUSD.r) is allowed
   if(StringFind(_Symbol, ResearchName) != 0 && !(ResearchName == "XAUUSD" && StringFind(_Symbol, "GOLD") == 0))
     {
      PrintFormat("ResearchName %s does not match the tested symbol %s: set it in Inputs", ResearchName, _Symbol);
      return INIT_FAILED;
     }
   if(!Load())
     {
      PrintFormat("no trade for %s in %s: check ResearchName and the file", ResearchName, TradesFile);
      return INIT_FAILED;
     }
   trade.SetExpertMagicNumber(20261103);
   trade.SetDeviationInPoints(100000);  // always fill at the market, as the research model does
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   PrintFormat("%s: %d trades to replay on %s, first %s, last %s", ResearchName, ArraySize(rows),
               _Symbol, TimeToString(rows[0].entry_time), TimeToString(rows[ArraySize(rows) - 1].entry_time));
   return INIT_SUCCEEDED;
  }

void Open(const int i)
  {
   MqlTick t;
   SymbolInfoTick(_Symbol, t);
   rows[i].open_time = t.time;
   rows[i].open_bid  = t.bid;
   rows[i].open_ask  = t.ask;
   int shift = iBarShift(_Symbol, PERIOD_M1, rows[i].entry_time - 60, true);
   rows[i].m1_close  = shift >= 0 ? iClose(_Symbol, PERIOD_M1, shift) : 0.0;
   ENUM_ORDER_TYPE type = rows[i].dir > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double pl = 0.0;
   rows[i].risk_money = OrderCalcProfit(type, _Symbol, Lots, rows[i].entry, rows[i].sl, pl) ? MathAbs(pl) : 0.0;
   string comment = IntegerToString(rows[i].id);
   bool ok = rows[i].dir > 0 ? trade.Buy(Lots, _Symbol, 0.0, rows[i].sl, rows[i].tp, comment)
                             : trade.Sell(Lots, _Symbol, 0.0, rows[i].sl, rows[i].tp, comment);
   if(!ok || trade.ResultRetcode() != TRADE_RETCODE_DONE || !HistoryDealSelect(trade.ResultDeal()))
     {
      rows[i].state = FAILED;
      rows[i].note  = "retcode " + IntegerToString(trade.ResultRetcode());
      return;
     }
   rows[i].position   = (ulong)HistoryDealGetInteger(trade.ResultDeal(), DEAL_POSITION_ID);
   rows[i].open_price = trade.ResultPrice();
   rows[i].state      = OPEN;
   int n = ArraySize(open_rows);
   ArrayResize(open_rows, n + 1, 256);
   open_rows[n] = i;
  }

// Fills the close fields from the position's deals.
void Collect(const int i)
  {
   rows[i].profit = rows[i].commission = rows[i].fee = rows[i].swap = 0.0;
   if(!HistorySelectByPosition(rows[i].position))
      return;
   for(int k = 0; k < HistoryDealsTotal(); k++)
     {
      ulong d = HistoryDealGetTicket(k);
      rows[i].commission += HistoryDealGetDouble(d, DEAL_COMMISSION);
      rows[i].fee        += HistoryDealGetDouble(d, DEAL_FEE);
      rows[i].swap       += HistoryDealGetDouble(d, DEAL_SWAP);
      rows[i].profit     += HistoryDealGetDouble(d, DEAL_PROFIT);
      ENUM_DEAL_ENTRY e = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY)
        {
         rows[i].close_time  = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         rows[i].close_price = HistoryDealGetDouble(d, DEAL_PRICE);
         ENUM_DEAL_REASON r  = (ENUM_DEAL_REASON)HistoryDealGetInteger(d, DEAL_REASON);
         rows[i].close_reason = r == DEAL_REASON_SL ? "sl" : r == DEAL_REASON_TP ? "tp"
                              : r == DEAL_REASON_EXPERT ? "time" : EnumToString(r);
        }
     }
   rows[i].state = CLOSED;
  }

void OnTick()
  {
   datetime now = TimeCurrent();
   int n = ArraySize(rows);
   while(next_row < n && rows[next_row].entry_time <= now)
      Open(next_row++);
   for(int k = ArraySize(open_rows) - 1; k >= 0; k--)
     {
      int i = open_rows[k];
      if(PositionSelectByTicket(rows[i].position))
        {
         if(now < rows[i].exit_time || !trade.PositionClose(rows[i].position))
            continue;
        }
      Collect(i);
      ArrayRemove(open_rows, k, 1);
     }
  }

string Px(const double v) { return DoubleToString(v, _Digits); }
string Tm(const datetime t) { return t > 0 ? TimeToString(t, TIME_DATE | TIME_SECONDS) : ""; }

void OnDeinit(const int reason)
  {
   if(reason == REASON_INITFAILED || ArraySize(rows) == 0)
      return;  // keep the file of an earlier good run
   string file = "mt5_replay_" + ResearchName + ".csv";
   int h = FileOpen(file, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("cannot write <Common>/Files/%s: error %d", file, GetLastError());
      return;
     }
   FileWriteString(h, "id,status,note,open_time,open_bid,open_ask,open_price,m1_close,close_time,"
                      "close_price,close_reason,profit,commission,fee,swap,risk_money\r\n");
   int counts[4] = {0, 0, 0, 0};
   for(int i = 0; i < ArraySize(rows); i++)
     {
      string status = rows[i].state == WAITING ? "not_reached" : rows[i].state == OPEN ? "open_at_end"
                    : rows[i].state == CLOSED ? "closed" : "failed";
      counts[rows[i].state]++;
      FileWriteString(h, IntegerToString(rows[i].id) + "," + status + "," + rows[i].note + ","
                      + Tm(rows[i].open_time) + "," + Px(rows[i].open_bid) + "," + Px(rows[i].open_ask) + ","
                      + Px(rows[i].open_price) + "," + Px(rows[i].m1_close) + "," + Tm(rows[i].close_time) + ","
                      + Px(rows[i].close_price) + "," + rows[i].close_reason + ","
                      + DoubleToString(rows[i].profit, 2) + "," + DoubleToString(rows[i].commission, 2) + ","
                      + DoubleToString(rows[i].fee, 2) + "," + DoubleToString(rows[i].swap, 2) + ","
                      + DoubleToString(rows[i].risk_money, 2) + "\r\n");
     }
   FileClose(h);
   PrintFormat("%s: closed %d, failed %d, open at the end %d, not reached %d; wrote <Common>/Files/%s",
               ResearchName, counts[CLOSED], counts[FAILED], counts[OPEN], counts[WAITING], file);
  }
//+------------------------------------------------------------------+
