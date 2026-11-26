import os
import requests
import pandas as pd
import yfinance as yf

SYMBOL = "GBPUSD=X"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def telecharger(interval, period):
    df = yf.download(SYMBOL, period=period, interval=interval,
                     auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


def envoyer(texte):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": texte},
        timeout=20,
    )


# Pivots de la semaine précédente
j = telecharger("1d", "1mo")
idx = pd.DatetimeIndex(j.index)
if idx.tz is not None:
    idx = idx.tz_convert(None)
semaines = idx.to_period("W")
courante = pd.Timestamp.now(tz="UTC").tz_convert(None).to_period("W")
sem = j[semaines == semaines[semaines < courante].max()]

H = sem["High"].max()
L = sem["Low"].min()
C = sem["Close"].iloc[-1]
P = (H + L + C) / 3
niveaux = {
    "R3": H + 2 * (P - L),
    "R2": P + (H - L),
    "R1": 2 * P - L,
    "P": P,
    "S1": 2 * P - H,
    "S2": P - (H - L),
    "S3": L - 2 * (H - P),
}

if os.environ.get("MANUEL") == "1":
    lignes = [f"{n} = {v:.5f}" for n, v in niveaux.items()]
    envoyer("Robot actif. Pivots GBP/USD :\n" + "\n".join(lignes))

# Dernières bougies 1H clôturées
h = telecharger("1h", "5d")
if h.index.tz is None:
    h.index = h.index.tz_localize("UTC")
maintenant = pd.Timestamp.now(tz="UTC")
h = h[h.index + pd.Timedelta(hours=1) <= maintenant]
if len(h) < 2 or maintenant - h.index[-1] > pd.Timedelta(hours=2):
    raise SystemExit("Marché fermé ou données insuffisantes")

avant = h["Close"].iloc[-2]
apres = h["Close"].iloc[-1]
for nom, v in niveaux.items():
    if avant < v <= apres:
        envoyer(f"GBP/USD : clôture 1H AU-DESSUS de {nom} ({v:.5f}). Clôture : {apres:.5f}")
    elif apres < v <= avant:
        envoyer(f"GBP/USD : clôture 1H EN DESSOUS de {nom} ({v:.5f}). Clôture : {apres:.5f}")
