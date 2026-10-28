//+------------------------------------------------------------------+
//| ExportSwaps.mq5: the MT5 swap export of                           |
//| ai-service/docs/strategies/PREREG.md, section 6a.                 |
//|                                                                   |
//| Run once as a script on the FxPro account (Navigator > Scripts).  |
//| Writes two files to <MT5 data folder>/MQL5/Files:                 |
//|   swaps.json       symbol -> the SwapSpec fields, read by         |
//|                    `python -m app strategies count --swaps`       |
//|   swaps_meta.json  every other section 6a field (account, server  |
//|                    clock, calc mode, digits, ticks), for the      |
//|                    record                                         |
//| One dated snapshot (W1): it says nothing about past rates.        |
//| Day multipliers (SYMBOL_SWAP_MONDAY...) are not read: older       |
//| builds lack them; add them by hand if the terminal shows them.    |
//+------------------------------------------------------------------+
#property script_show_inputs

// The research name of each instrument and its exact name in this account (edit a suffix,
// e.g. "XAUUSD.r", here).
input string XAUUSD_name = "XAUUSD";
input string EURUSD_name = "EURUSD";
input string GBPUSD_name = "GBPUSD";
input string USDJPY_name = "USDJPY";
input string AUDUSD_name = "AUDUSD";
input string USDCAD_name = "USDCAD";

string Num(const double v) { return DoubleToString(v, 10); }
string Str(const string s) { return "\"" + s + "\""; }

// "SYMBOL_SWAP_MODE_POINTS" -> "POINTS", as app/strategies/swap.py names the modes
string SwapMode(const string sym)
  {
   string s = EnumToString((ENUM_SYMBOL_SWAP_MODE)SymbolInfoInteger(sym, SYMBOL_SWAP_MODE));
   return StringSubstr(s, StringLen("SYMBOL_SWAP_MODE_"));
  }

bool Write(const string file, const string text)
  {
   int h = FileOpen(file, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
     {
      Print("cannot write ", file, ": error ", GetLastError());
      return false;
     }
   FileWriteString(h, text);
   FileClose(h);
   return true;
  }

void OnStart()
  {
   string research[] = {"XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"};
   string broker[6];
   broker[0] = XAUUSD_name; broker[1] = EURUSD_name; broker[2] = GBPUSD_name;
   broker[3] = USDJPY_name; broker[4] = AUDUSD_name; broker[5] = USDCAD_name;
   string deposit = AccountInfoString(ACCOUNT_CURRENCY);

   string swaps = "{\n", meta = "{\n";
   meta += "  \"_account\": {\"currency\": " + Str(deposit)
         + ", \"server\": " + Str(AccountInfoString(ACCOUNT_SERVER))
         + ", \"company\": " + Str(AccountInfoString(ACCOUNT_COMPANY))
         + ", \"trade_mode\": " + Str(EnumToString((ENUM_ACCOUNT_TRADE_MODE)
                                       AccountInfoInteger(ACCOUNT_TRADE_MODE)))
         + ", \"margin_mode\": " + Str(EnumToString((ENUM_ACCOUNT_MARGIN_MODE)
                                        AccountInfoInteger(ACCOUNT_MARGIN_MODE)))
         + ", \"time_trade_server\": " + Str(TimeToString(TimeTradeServer(), TIME_DATE | TIME_SECONDS))
         + ", \"time_gmt\": " + Str(TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS))
         + ", \"terminal_build\": " + IntegerToString(TerminalInfoInteger(TERMINAL_BUILD))
         + ", \"account_type_and_swap_free\": \"fill in by hand: Standard or Raw, swap-free or not\"}";

   int written = 0;
   for(int i = 0; i < 6; i++)
     {
      string sym = broker[i];
      if(!SymbolSelect(sym, true))
        {
         Print(research[i], ": symbol ", sym, " not found; fix its input name");
         continue;
        }
      string sep = written > 0 ? ",\n" : "";
      swaps += sep + "  " + Str(research[i]) + ": {"
             + "\"mode\": " + Str(SwapMode(sym))
             + ", \"long\": " + Num(SymbolInfoDouble(sym, SYMBOL_SWAP_LONG))
             + ", \"short\": " + Num(SymbolInfoDouble(sym, SYMBOL_SWAP_SHORT))
             + ", \"rollover3days\": " + IntegerToString(SymbolInfoInteger(sym, SYMBOL_SWAP_ROLLOVER3DAYS))
             + ", \"point\": " + Num(SymbolInfoDouble(sym, SYMBOL_POINT))
             + ", \"contract_size\": " + Num(SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE))
             + ", \"currency_base\": " + Str(SymbolInfoString(sym, SYMBOL_CURRENCY_BASE))
             + ", \"currency_profit\": " + Str(SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT))
             + ", \"currency_margin\": " + Str(SymbolInfoString(sym, SYMBOL_CURRENCY_MARGIN))
             + ", \"deposit_currency\": " + Str(deposit) + "}";
      meta += ",\n  " + Str(research[i]) + ": {"
            + "\"broker_symbol\": " + Str(sym)
            + ", \"trade_calc_mode\": " + Str(EnumToString((ENUM_SYMBOL_CALC_MODE)
                                              SymbolInfoInteger(sym, SYMBOL_TRADE_CALC_MODE)))
            + ", \"digits\": " + IntegerToString(SymbolInfoInteger(sym, SYMBOL_DIGITS))
            + ", \"tick_size\": " + Num(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE))
            + ", \"tick_value\": " + Num(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE)) + "}";
      written++;
     }
   swaps += "\n}\n";
   meta += "\n}\n";
   if(Write("swaps.json", swaps) && Write("swaps_meta.json", meta))
      Print("wrote swaps.json and swaps_meta.json for ", written, " of 6 symbols to ",
            TerminalInfoString(TERMINAL_DATA_PATH), "\\MQL5\\Files");
  }
