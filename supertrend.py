import os
import numpy as np
import pandas as pd
import requests
import yfinance as yf

SYMBOL = "GBPUSD=X"
PRD = 2          # Pivot Point Period
FACTOR = 3.0     # ATR Factor
ATR_PERIOD = 10  # ATR Period
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def envoyer(texte):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": texte},
        timeout=20,
    )


def calcul(df):
    high, low, close = df["High"], df["Low"], df["Close"]
    n = len(df)

    # Pivots (confirmés PRD bougies plus tard, comme dans Pine)
    hs = high.shift(PRD)
    ls = low.shift(PRD)
    ph = hs.where(hs == high.rolling(2 * PRD + 1).max()).to_numpy()
    pl = ls.where(ls == low.rolling(2 * PRD + 1).min()).to_numpy()

    # ATR (moyenne de Wilder, comme atr() de Pine)
    tr = pd.concat([high - low,
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1).to_numpy()
    atr = np.full(n, np.nan)
    if n >= ATR_PERIOD:
        atr[ATR_PERIOD - 1] = tr[:ATR_PERIOD].mean()
        for i in range(ATR_PERIOD, n):
            atr[i] = (atr[i - 1] * (ATR_PERIOD - 1) + tr[i]) / ATR_PERIOD

    c = close.to_numpy()
    tup = np.full(n, np.nan)
    tdn = np.full(n, np.nan)
    trend = np.ones(n, dtype=int)
    center = np.nan

    for i in range(n):
        pp = ph[i] if not np.isnan(ph[i]) else pl[i]
        if not np.isnan(pp):
            center = pp if np.isnan(center) else (center * 2 + pp) / 3
        up = center - FACTOR * atr[i]
        dn = center + FACTOR * atr[i]

        if i > 0 and c[i - 1] > tup[i - 1]:
            tup[i] = max(up, tup[i - 1])
        else:
            tup[i] = up
        if i > 0 and c[i - 1] < tdn[i - 1]:
            tdn[i] = min(dn, tdn[i - 1])
        else:
            tdn[i] = dn

        if i > 0 and c[i] > tdn[i - 1]:
            trend[i] = 1
        elif i > 0 and c[i] < tup[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1] if i > 0 else 1

    stop = np.where(trend == 1, tup, tdn)
    return trend, stop, c


df = yf.download(SYMBOL, period="60d", interval="1h",
                 auto_adjust=False, progress=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
df = df.dropna()
if df.index.tz is None:
    df.index = df.index.tz_localize("UTC")

# Garder uniquement les bougies 1H clôturées
maintenant = pd.Timestamp.now(tz="UTC")
df = df[df.index + pd.Timedelta(hours=1) <= maintenant]
if len(df) < 50:
    raise SystemExit("Données insuffisantes")

trend, stop, c = calcul(df)

if os.environ.get("MANUEL") == "1":
    sens = "haussière" if trend[-1] == 1 else "baissière"
    envoyer(f"Robot Supertrend actif. Tendance 1H : {sens}. "
            f"Stop suiveur : {stop[-1]:.5f}")

if maintenant - df.index[-1] > pd.Timedelta(hours=2):
    raise SystemExit("Marché fermé")

if trend[-1] == 1 and trend[-2] == -1:
    envoyer(f"GBP/USD 1H : signal ACHAT (Pivot Point SuperTrend). "
            f"Clôture : {c[-1]:.5f} | Stop suiveur : {stop[-1]:.5f}")
elif trend[-1] == -1 and trend[-2] == 1:
    envoyer(f"GBP/USD 1H : signal VENTE (Pivot Point SuperTrend). "
            f"Clôture : {c[-1]:.5f} | Stop suiveur : {stop[-1]:.5f}")
