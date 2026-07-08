from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import pandas as pd

app = FastAPI()

# CORS für deine Website freigeben
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_gamma_exposure(ticker="SPY"):
    """
    Berechnet GEX für SPY (Proxy für S&P 500 Futures)
    """
    stock = yf.Ticker(ticker)
    spot_price = stock.history(period="1d")['Close'].iloc[-1]
    
    # Alle Verfallstermine der nächsten 45 Tage
    expirations = stock.options
    
    all_gamma = []
    all_data = []
    
    for exp_date in expirations[:3]:  # Nur nächste 3 Verfallstermine für Speed
        try:
            chain = stock.option_chain(exp_date)
            calls = chain.calls
            puts = chain.puts
            
            # Nur Strikes ±10% um Spot
            calls = calls[(calls['strike'] >= spot_price * 0.9) & 
                         (calls['strike'] <= spot_price * 1.1)]
            puts = puts[(puts['strike'] >= spot_price * 0.9) & 
                       (puts['strike'] <= spot_price * 1.1)]
            
            for _, row in calls.iterrows():
                gamma = row.get('gamma', 0)
                if pd.notna(gamma) and gamma > 0:
                    oi = row.get('openInterest', 0)
                    if pd.notna(oi) and oi > 0:
                        gex = gamma * oi * row['strike'] * 100
                        all_data.append({
                            'strike': row['strike'],
                            'type': 'call',
                            'gamma': gamma,
                            'oi': oi,
                            'gex': gex
                        })
                        all_gamma.append(gex)
            
            for _, row in puts.iterrows():
                gamma = row.get('gamma', 0)
                if pd.notna(gamma) and gamma > 0:
                    oi = row.get('openInterest', 0)
                    if pd.notna(oi) and oi > 0:
                        gex = -gamma * oi * row['strike'] * 100  # Minus für Puts
                        all_data.append({
                            'strike': row['strike'],
                            'type': 'put',
                            'gamma': gamma,
                            'oi': oi,
                            'gex': gex
                        })
                        all_gamma.append(gex)
        except:
            continue
    
    df = pd.DataFrame(all_data)
    
    if df.empty:
        return None
    
    # Gruppieren nach Strike
    strike_gex = df.groupby('strike')['gex'].sum().reset_index()
    strike_gex = strike_gex.sort_values('strike')
    
    # Kumulative Summe
    strike_gex['cumulative_gex'] = strike_gex['gex'].cumsum()
    
    # Zero Gamma Level (wo kumulativ = 0)
    zero_gamma_idx = np.argmin(np.abs(strike_gex['cumulative_gex']))
    zero_gamma = float(strike_gex.iloc[zero_gamma_idx]['strike'])
    
    # Net GEX
    net_gex = float(strike_gex['gex'].sum())
    
    # Call Wall (höchstes positives Gamma)
    call_wall = float(strike_gex[strike_gex['gex'] > 0].nlargest(1, 'gex')['strike'].iloc[0]) if len(strike_gex[strike_gex['gex'] > 0]) > 0 else spot_price * 1.05
    
    # Put Wall (höchstes negatives Gamma)
    put_wall = float(strike_gex[strike_gex['gex'] < 0].nsmallest(1, 'gex')['strike'].iloc[0]) if len(strike_gex[strike_gex['gex'] < 0]) > 0 else spot_price * 0.95
    
    # Gamma Flip Point (erster Strike unter Spot wo Gamma negativ wird)
    below_spot = strike_gex[strike_gex['strike'] <= spot_price]
    gamma_flip = float(spot_price)
    for _, row in below_spot.iloc[::-1].iterrows():
        if row['cumulative_gex'] < 0:
            gamma_flip = float(row['strike'])
            break
    
    # Status
    if net_gex > 500_000_000:  # > 500 Mio positiv
        status = "positive"
    elif net_gex < -500_000_000:  # < -500 Mio negativ
        status = "negative"
    else:
        status = "neutral"
    
    # Gamma Profil für Chart
    gamma_profile = []
    for _, row in strike_gex.iterrows():
        gamma_profile.append({
            'strike': float(row['strike']),
            'gex_millions': float(row['gex'] / 1_000_000),
            'cumulative_gex_millions': float(row['cumulative_gex'] / 1_000_000)
        })
    
    result = {
        'spot_price': float(spot_price),
        'net_gex_millions': float(net_gex / 1_000_000),
        'net_gex_billions': round(float(net_gex / 1_000_000_000), 3),
        'zero_gamma': zero_gamma,
        'call_wall': call_wall,
        'put_wall': put_wall,
        'gamma_flip': gamma_flip,
        'status': status,
        'gamma_profile': gamma_profile,
        'timestamp': datetime.now().isoformat(),
        'total_call_gamma_millions': float(df[df['type']=='call']['gex'].sum() / 1_000_000),
        'total_put_gamma_millions': float(abs(df[df['type']=='put']['gex'].sum()) / 1_000_000),
    }
    
    return result


@app.get("/")
def root():
    return {"status": "GEX Backend läuft", "docs": "/docs"}


@app.get("/api/gex")
def get_gex():
    """Gibt aktuellen GEX zurück"""
    data = calculate_gamma_exposure("SPY")
    if data is None:
        return {"error": "Keine Optionsdaten verfügbar"}
    return data


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
