//+------------------------------------------------------------------+
//| ExportHistory.mq5: downloads and exports the M1 history of the    |
//| Addendum 2 confirmation instruments                               |
//| (ai-service/docs/strategies/ADDENDUM_2_LEVEL_BREAK.md, section 4).|
//|                                                                   |
//| Run once as a script on the FxPro account (Navigator > Scripts).  |
//| For each symbol it asks the server for the history month by month |
//| (a long range at once returns nothing), then writes the bars in   |
//| the MT5 "Export Bars" format to <Common>/Files/history/:          |
//|   <RESEARCH>_M1_<first>_<last>.csv  (server time, tab separated)  |
//|   history_meta_<time>.json (point, digits, contract size, ...)  |
//| read by `python -m app import --raw-dir <that folder>`.           |
//| The range ends before the lockbox start (2026-01-10), so no bar   |
//| of the lockbox is written.                                        |
//| GOLD_name (empty by default): FxPro's own gold, the feed the v1   |
//| demo trades (docs/strategies/GOLD_V1.md), written as GOLDFX_M1_*; |
//| for it To may run past the lockbox start, which the gold exam has |
//| opened already. Leave the other names empty to export it alone.   |
//+------------------------------------------------------------------+
#property script_show_inputs

// The research name of each instrument and its exact name in this account (FxPro calls gold
// GOLD; silver may be SILVER). Leave a name empty to skip that instrument.
input string NZDUSD_name = "NZDUSD";
input string USDCHF_name = "USDCHF";
input string EURJPY_name = "EURJPY";
input string GBPJPY_name = "GBPJPY";
input string EURGBP_name = "EURGBP";
input string XAGUSD_name = "SILVER";
input string GOLD_name   = "";                    // "GOLD": FxPro gold for the v1 check
input datetime From      = D'2010.01.01 00:00';
input datetime To        = D'2026.01.09 23:59';   // the day before the lockbox start
input string   Folder    = "history";            // in <Common>/Files

string Str(const string s) { return "\"" + s + "\""; }

datetime MonthStart(const datetime t)
  {
   MqlDateTime d;
   TimeToStruct(t, d);
   d.day = 1; d.hour = 0; d.min = 0; d.sec = 0;
   return StructToTime(d);
  }

datetime NextMonth(const datetime t)
  {
   MqlDateTime d;
   TimeToStruct(t, d);
   d.mon++;
   if(d.mon > 12) { d.mon = 1; d.year++; }
   d.day = 1; d.hour = 0; d.min = 0; d.sec = 0;
   return StructToTime(d);
  }

// The bars of [a, b]; asks again until two answers agree (the server sends history in parts).
int Fetch(const string sym, const datetime a, const datetime b, MqlRates &rates[])
  {
   int prev = -2;
   for(int k = 0; k < 40 && !IsStopped(); k++)
     {
      ResetLastError();
      int n = CopyRates(sym, PERIOD_M1, a, b, rates);
      if(n == prev && (n > 0 || k >= 4))
         return MathMax(n, 0);
      prev = n;
      Sleep(300);
     }
   return MathMax(prev, 0);
  }

string Line(const MqlRates &r, const int digits)
  {
   return TimeToString(r.time, TIME_DATE) + "\t" + TimeToString(r.time, TIME_SECONDS) + "\t"
        + DoubleToString(r.open, digits) + "\t" + DoubleToString(r.high, digits) + "\t"
        + DoubleToString(r.low, digits) + "\t" + DoubleToString(r.close, digits) + "\t"
        + IntegerToString(r.tick_volume) + "\t" + IntegerToString(r.real_volume) + "\t"
        + IntegerToString(r.spread) + "\r\n";
  }

string Stamp(const datetime t)  // YYYYMMDDHHMM, as the file names of "Export Bars"
  {
   MqlDateTime d;
   TimeToStruct(t, d);
   return StringFormat("%04d%02d%02d%02d%02d", d.year, d.mon, d.day, d.hour, d.min);
  }

// Exports one symbol; returns its meta JSON entry, or "" when nothing was written.
string Export(const string research, const string sym)
  {
   if(sym == "")
      return "";
   if(!SymbolSelect(sym, true))
     {
      PrintFormat("%s: symbol %s not found in this account; fix its input name", research, sym);
      return "";
     }
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   string tmp = Folder + "\\" + research + "_M1_partial.csv";
   int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("%s: cannot write %s: error %d", research, tmp, GetLastError());
      return "";
     }
   FileWriteString(h, "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\r\n");
   datetime first = 0, last = 0;
   long total = 0;
   MqlRates rates[];
   // start at the server's first M1 bar, so the empty years before it are not asked for
   datetime begin = From;
   for(int k = 0; k < 20 && !IsStopped(); k++)
     {
      datetime f = (datetime)SeriesInfoInteger(sym, PERIOD_M1, SERIES_SERVER_FIRSTDATE);
      if(f > 0)
        {
         if(f > begin)
            begin = f;
         break;
        }
      Sleep(300);
     }
   PrintFormat("%s (%s): starting at %s", research, sym, TimeToString(begin));
   for(datetime m = MonthStart(begin); m <= To && !IsStopped(); m = NextMonth(m))
     {
      datetime a = m < From ? From : m;
      datetime end = NextMonth(m) - 1;
      if(end > To)
         end = To;
      int n = Fetch(sym, a, end, rates);
      for(int i = 0; i < n; i++)
        {
         if(rates[i].time < From || rates[i].time > To || rates[i].time <= last)
            continue;
         FileWriteString(h, Line(rates[i], digits));
         if(first == 0)
            first = rates[i].time;
         last = rates[i].time;
         total++;
        }
      Comment(research, ": ", TimeToString(m, TIME_DATE), "  bars so far ", total);
     }
   FileClose(h);
   if(total == 0)
     {
      PrintFormat("%s: no bars received; check Tools > Options > Charts > Max. bars in chart (Unlimited)", research);
      FileDelete(tmp, FILE_COMMON);
      return "";
     }
   string name = Folder + "\\" + research + "_M1_" + Stamp(first) + "_" + Stamp(last) + ".csv";
   if(!FileMove(tmp, FILE_COMMON, name, FILE_REWRITE | FILE_COMMON))
      PrintFormat("%s: cannot rename to %s: error %d", research, name, GetLastError());
   PrintFormat("%s (%s): %I64d bars, %s to %s -> <Common>/Files/%s", research, sym, total,
               TimeToString(first), TimeToString(last), name);
   return Str(research) + ": {\"broker_name\": " + Str(sym)
        + ", \"point\": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_POINT), 10)
        + ", \"digits\": " + IntegerToString(digits)
        + ", \"contract_size\": " + DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE), 2)
        + ", \"currency_base\": " + Str(SymbolInfoString(sym, SYMBOL_CURRENCY_BASE))
        + ", \"currency_profit\": " + Str(SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT))
        + ", \"bars\": " + IntegerToString(total)
        + ", \"first_server\": " + Str(TimeToString(first)) + ", \"last_server\": " + Str(TimeToString(last)) + "}";
  }

void OnStart()
  {
   long maxbars = TerminalInfoInteger(TERMINAL_MAXBARS);
   if(maxbars < 10000000)
      PrintFormat("Max. bars in chart is %I64d: set it to Unlimited (Tools > Options > Charts) and restart MT5 if bars are missing", maxbars);
   string research[] = {"NZDUSD", "USDCHF", "EURJPY", "GBPJPY", "EURGBP", "XAGUSD", "GOLDFX"};
   string broker[7];
   broker[0] = NZDUSD_name; broker[1] = USDCHF_name; broker[2] = EURJPY_name;
   broker[3] = GBPJPY_name; broker[4] = EURGBP_name; broker[5] = XAGUSD_name; broker[6] = GOLD_name;
   string meta = "{\n  \"_export\": {\"server\": " + Str(AccountInfoString(ACCOUNT_SERVER))
               + ", \"from\": " + Str(TimeToString(From)) + ", \"to\": " + Str(TimeToString(To))
               + ", \"terminal_build\": " + IntegerToString(TerminalInfoInteger(TERMINAL_BUILD)) + "}";
   for(int i = 0; i < 7 && !IsStopped(); i++)
     {
      string e = Export(research[i], broker[i]);
      if(e != "")
         meta += ",\n  " + e;
     }
   meta += "\n}\n";
   // one meta file per run, so a second run for the remaining symbols keeps the first one's
   int h = FileOpen(Folder + "\\history_meta_" + Stamp(TimeLocal()) + ".json",
                    FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h != INVALID_HANDLE)
     {
      FileWriteString(h, meta);
      FileClose(h);
     }
   Comment("");
   Print("ExportHistory done: <Common>/Files/", Folder);
  }
//+------------------------------------------------------------------+
