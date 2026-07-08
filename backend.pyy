# ============================================
# GEX BACKEND - Komplett in einer Datei
# ============================================

# === 1. Abhängigkeiten installieren ===
import subprocess, sys, os

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    from fastapi import FastAPI
except:
    packages = ["fastapi", "uvicorn", "yfinance", "numpy", "pandas"]
    for p in packages:
        install(p)

# === 2. API starten ===
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import numpy as np
from datetime import datetime
import pandas as pd

app = FastAPI()

# CORS - erlaubt Zugriff von deiner Website
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "name": "GEX Backend",
        "status": "läuft",
        "endpoints": ["/api/gex"]
    }

@app.get("/api/gex")
def get_gex():
    """
    Holt echte Optionsdaten und berechnet Gamma Exposure
    """
    try:
        # SPY als Proxy für S&P 500 Futures
        stock = yf.Ticker("SPY")
        spot = stock.history(period="1d")['Close'].iloc[-1]
        
        # Optionsdaten holen
        expirations = stock.options[:3]  # Nächste 3 Verfallstermine
        all_data = []
        
        for exp in expirations:
            try:
                chain = stock.option_chain(exp)
                
                # Calls durchgehen
                for _, row in chain.calls.iterrows():
                    if row['strike'] >= spot*0.9 and row['strike'] <= spot*1.1:
                        gamma = row.get('gamma', 0) or 0
                        oi = row.get('openInterest', 0) or 0
                        gex = gamma * oi * row['strike'] * 100
                        all_data.append({
                            'strike': row['strike'],
                            'gex': gex,
                            'type': 'call'
                        })
                
                # Puts durchgehen
                for _, row in chain.puts.iterrows():
                    if row['strike'] >= spot*0.9 and row['strike'] <= spot*1.1:
                        gamma = row.get('gamma', 0) or 0
                        oi = row.get('openInterest', 0) or 0
                        gex = -gamma * oi * row['strike'] * 100  # Minus für Puts
                        all_data.append({
                            'strike': row['strike'],
                            'gex': gex,
                            'type': 'put'
                        })
            except:
                continue
        
        if not all_data:
            return {
                "error": "Keine Optionsdaten verfügbar",
                "spot_price": float(spot),
                "timestamp": datetime.now().isoformat()
            }
        
        # Daten gruppieren und berechnen
        df = pd.DataFrame(all_data)
        df_grouped = df.groupby('strike')['gex'].sum().reset_index()
        df_grouped = df_grouped.sort_values('strike')
        df_grouped['cumulative_gex'] = df_grouped['gex'].cumsum()
        
        # === WICHTIGE WERTE ===
        
        # Net GEX
        net_gex = float(df_grouped['gex'].sum())
        
        # Zero Gamma Level (wo kumulatives Gamma = 0)
        zero_gamma_idx = np.argmin(np.abs(df_grouped['cumulative_gex']))
        zero_gamma = float(df_grouped.iloc[zero_gamma_idx]['strike'])
        
        # Gamma Flip (wo Gamma unter Spot negativ wird)
        gamma_flip = float(spot)
        below_spot = df_grouped[df_grouped['strike'] <= spot]
        for _, row in below_spot.iloc[::-1].iterrows():
            if row['cumulative_gex'] < 0:
                gamma_flip = float(row['strike'])
                break
        
        # Call Wall & Put Wall
        calls = df_grouped[df_grouped['gex'] > 0]
        puts = df_grouped[df_grouped['gex'] < 0]
        
        call_wall = float(calls.nlargest(1, 'gex')['strike'].iloc[0]) if len(calls) > 0 else spot * 1.05
        put_wall = float(puts.nsmallest(1, 'gex')['strike'].iloc[0]) if len(puts) > 0 else spot * 0.95
        
        # Status
        if net_gex > 500_000_000:
            status = "positive"
        elif net_gex < -500_000_000:
            status = "negative"
        else:
            status = "neutral"
        
        # Gamma Profil für Chart (Top 20 Strikes)
        profile = []
        for _, row in df_grouped.iterrows():
            profile.append({
                'strike': float(row['strike']),
                'gex_millions': round(float(row['gex']) / 1_000_000, 2),
                'cumulative_millions': round(float(row['cumulative_gex']) / 1_000_000, 2)
            })
        
        return {
            'spot_price': float(spot),
            'net_gex_billions': round(net_gex / 1_000_000_000, 3),
            'net_gex_millions': round(net_gex / 1_000_000, 0),
            'zero_gamma': zero_gamma,
            'gamma_flip': gamma_flip,
            'call_wall': call_wall,
            'put_wall': put_wall,
            'status': status,
            'gamma_profile': profile[:30],  # Top 30 Strikes
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# === 3. Start-Befehl (für Render) ===
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
