# Murphy Scanner 📊

סורק מניות מבוסס תורת ג'ון מרפי:
- Technical Analysis of the Financial Markets
- Intermarket Analysis

## התקנה והפעלה

```bash
pip install -r requirements.txt
streamlit run app.py
```

## מה הסורק עושה

### Tab 1 - מצב השוק
- מדדים ראשיים (SPY, QQQ, IWM, DIA)
- אינטרמרקט: דולר, אג"ח, זהב, נפט
- Sector Rotation + פרשנות לפי מרפי

### Tab 2 - Trend Following
קריטריונים (לפי מרפי):
- Close > SMA50 > SMA200
- Volume Ratio מקסימלי 5 ימים ≥ 1.5
- לא בתוך 3% מהתנגדות אופקית 6 חודשים
- ממוין לפי RS Slope vs SPY

### Tab 3 - Mean Reversion
- RSI יומי < 30 (Oversold) או > 70 (Overbought)
- Institutional Breakdown Trap: Weekly RSI שבר < 50
- Bullish/Bearish Failure Swing עם אישור מחיר

### Tab 4 - ניתוח וביצוע
- גרף נרות יפניים + SMA50/200 + RSI
- זיהוי Gap + Measuring Rule Target
- כניסה מפוצלת 50/50
- Fibonacci 33%-50%-66% על Swing מלא
- Stop Loss = 2×ATR
- חישוב R:R + התראה אם < 1:2
