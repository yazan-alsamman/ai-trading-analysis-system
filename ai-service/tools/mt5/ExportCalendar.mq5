//+------------------------------------------------------------------+
//| ExportCalendar.mq5: the MT5 economic calendar with its history,   |
//| for ai-service/docs/discovery/PLAN.md, family F3 (news).          |
//|                                                                   |
//| Run once as a script on any MT5 account (Navigator > Scripts).    |
//| Writes <Common>/Files/calendar_history.csv, one row per release:  |
//|   time_server, time_utc, currency, country, event, importance,    |
//|   impact, actual, forecast, previous, revised, event_id, value_id |
//| Values are in the event's own unit (MT5's multiplier applied);    |
//| an empty cell is a value the calendar does not hold.              |
//| MT5 gives every calendar time at the server's offset *now* (not   |
//| the offset of that date), so time_server is not the server clock |
//| of the day, and time_utc (time - the offset now) is the true UTC. |
//| Checked 2026-11-11: NFP and CPI at 08:30 New York in 202 of 203   |
//| and 202 of 202 releases, summer and winter alike.                 |
//+------------------------------------------------------------------+
#property script_show_inputs

input datetime FromDate     = D'2010.01.01';
input string   Currencies   = "USD,EUR,GBP,JPY,CNY,CHF,CAD,AUD";  // empty: every currency
input int      MinImportance = 1;   // 0 none, 1 low, 2 moderate, 3 high
input string   FileName     = "calendar_history.csv";

string Val(const bool has, const double v) { return has ? DoubleToString(v, 6) : ""; }

string Clean(string s)
  {
   StringReplace(s, ",", ";");
   StringReplace(s, "\"", "'");
   return s;
  }

bool Wanted(const string cur, string &list[])
  {
   if(ArraySize(list) == 0)
      return true;
   for(int i = 0; i < ArraySize(list); i++)
      if(list[i] == cur)
         return true;
   return false;
  }

void OnStart()
  {
   string list[];
   if(StringLen(Currencies) > 0)
      StringSplit(Currencies, ',', list);
   int h = FileOpen(FileName, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
     {
      Print("cannot write ", FileName, ": error ", GetLastError());
      return;
     }
   FileWriteString(h, "time_server,time_utc,currency,country,event,importance,impact,actual,"
                      "forecast,previous,revised,event_id,value_id\r\n");
   long offset = (long)(TimeTradeServer() - TimeGMT());  // server - UTC, now
   datetime to = TimeTradeServer() + 30 * 86400;
   int rows = 0;
   datetime first = 0, last = 0;
   // a year at a time keeps each request small
   for(datetime a = FromDate; a < to; a += 365 * 86400)
     {
      datetime b = MathMin(a + 365 * 86400, to);
      MqlCalendarValue values[];
      ResetLastError();
      if(CalendarValueHistory(values, a, b) <= 0)
        {
         Print(TimeToString(a, TIME_DATE), ": no values (error ", GetLastError(), ")");
         continue;
        }
      for(int i = 0; i < ArraySize(values); i++)
        {
         MqlCalendarEvent ev;
         MqlCalendarCountry co;
         if(!CalendarEventById(values[i].event_id, ev) || !CalendarCountryById(ev.country_id, co))
            continue;
         if(ev.importance < MinImportance || !Wanted(co.currency, list))
            continue;
         datetime t = values[i].time;
         FileWriteString(h, StringFormat("%s,%s,%s,%s,%s,%d,%d,%s,%s,%s,%s,%I64u,%I64u\r\n",
            TimeToString(t, TIME_DATE | TIME_SECONDS),
            TimeToString((datetime)(t - offset), TIME_DATE | TIME_SECONDS),
            co.currency, Clean(co.name), Clean(ev.name), (int)ev.importance,
            (int)values[i].impact_type,
            Val(values[i].HasActualValue(), values[i].GetActualValue()),
            Val(values[i].HasForecastValue(), values[i].GetForecastValue()),
            Val(values[i].HasPreviousValue(), values[i].GetPreviousValue()),
            Val(values[i].HasRevisedValue(), values[i].GetRevisedValue()),
            ev.id, values[i].id));
         rows++;
         if(first == 0 || t < first)
            first = t;
         if(t > last)
            last = t;
        }
     }
   FileClose(h);
   Print("wrote ", rows, " releases from ", TimeToString(first, TIME_DATE), " to ",
         TimeToString(last, TIME_DATE), " to <Common>/Files/", FileName,
         " (server - UTC now: ", offset / 3600, " h)");
  }
