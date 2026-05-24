import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import plotly.graph_objects as go
import requests
import yfinance as yf
import pytz
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_percentage_error
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI Market Oracle Pro",
    layout="wide",
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

PKT = pytz.timezone("Asia/Karachi")

# ─────────────────────────────────────────────
#  CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0a0e1a;
    color: #e0e6f0;
}
.stApp { background: linear-gradient(135deg, #0a0e1a 0%, #0d1526 100%); }
h1, h2, h3 { font-family: 'Orbitron', monospace; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1526 0%, #111827 100%);
    border-right: 1px solid #1e2d45;
}
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #111827, #1a2540);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 4px 20px rgba(0,180,255,0.08);
}
.stTabs [data-baseweb="tab-list"] {
    background: #0d1526;
    border-radius: 10px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    color: #7a9cc4;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0062cc, #0098ff) !important;
    color: white !important;
}
.signal-badge {
    display:inline-block;
    padding: 6px 18px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 1px;
}
.buy  { background: rgba(0,200,83,0.15);  border:1px solid #00c853; color:#00c853; }
.sell { background: rgba(255,23,68,0.15); border:1px solid #ff1744; color:#ff1744; }
.hold { background: rgba(255,171,0,0.15); border:1px solid #ffab00; color:#ffab00; }
.bt-card {
    background: linear-gradient(135deg,#111827,#1a2540);
    border: 1px solid #1e3a5f;
    border-radius:12px; padding:14px 18px;
    margin:6px 0;
}
.bt-good  { color:#00e676; font-weight:700; }
.bt-ok    { color:#ffab00; font-weight:700; }
.bt-bad   { color:#ff5252; font-weight:700; }
.clock-box {
    background:#111827; border:1px solid #1e3a5f;
    border-radius:10px; padding:8px 14px;
    font-family:'Orbitron',monospace;
    font-size:13px; color:#00bcd4;
    text-align:center; margin-bottom:8px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def pkt_now():
    return datetime.now(PKT)

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def deep_clean_data(df):
    if df is None or df.empty:
        return None, None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    df.columns = [c.strip().title() for c in df.columns]
    target_col = next((c for c in ['Close', 'Price', '4. Close', 'Last'] if c in df.columns), None)
    if not target_col:
        st.sidebar.error(f"Close column nahi mila. Columns: {list(df.columns)}")
        return None, None
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('$', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce')
    if 'Date' not in df.columns:
        df = df.reset_index()
    # FIX: yfinance intraday index 'Datetime' hota hai, daily ka 'Date' — dono handle karo
    df.rename(columns={
        'index':    'Date',
        'date':     'Date',
        'Datetime': 'Date',
        'datetime': 'Date',
        'Timestamp':'Date',
    }, inplace=True)
    # Agar abhi bhi Date nahi mila to pehla column Date maan lo
    if 'Date' not in df.columns:
        df.rename(columns={df.columns[0]: 'Date'}, inplace=True)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=[target_col, 'Date'])
    return df.sort_values('Date').reset_index(drop=True), target_col

@st.cache_data(ttl=300)
def fetch_live_data(ticker, period="2y"):
    try:
        raw = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if raw.empty:
            return None, f"{ticker} ka data nahi mila"
        return raw, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=60)
def fetch_intraday_data(ticker):
    try:
        raw = yf.download(ticker, period="5d", interval="5m", auto_adjust=True, progress=False)
        if raw.empty:
            return None, "Intraday data nahi mila"
        return raw, None
    except Exception as e:
        return None, str(e)

# ─────────────────────────────────────────────
#  BACKTESTING ENGINE
# ─────────────────────────────────────────────
def run_backtest(clean_df, target, feature_cols, scaler, model):
    n = len(clean_df)
    train_size = int(n * 0.7)
    if train_size < 20:
        return None

    X_all = scaler.transform(clean_df[feature_cols])
    y_all = clean_df['Target'].values

    preds   = model.predict(X_all[train_size:])
    actuals = y_all[train_size:]
    prev_prices = clean_df[target].values[train_size:]

    correct_dir = 0
    trades = {"buy_win": 0, "buy_loss": 0, "sell_win": 0, "sell_loss": 0}

    for pred, actual, prev in zip(preds, actuals, prev_prices):
        pred_dir   = 1 if pred   > prev else -1
        actual_dir = 1 if actual > prev else -1
        if pred_dir == actual_dir:
            correct_dir += 1
        pct_pred   = (pred   - prev) / prev * 100
        pct_actual = (actual - prev) / prev * 100
        if pct_pred > 1:
            trades["buy_win" if pct_actual > 0 else "buy_loss"] += 1
        elif pct_pred < -1:
            trades["sell_win" if pct_actual < 0 else "sell_loss"] += 1

    dir_acc = (correct_dir / len(preds)) * 100
    try:
        mape = mean_absolute_percentage_error(actuals, preds) * 100
    except Exception:
        mape = 0

    total_signals = sum(trades.values())
    win_rate = (trades["buy_win"] + trades["sell_win"]) / total_signals * 100 if total_signals > 0 else 0

    return {
        "dir_accuracy": round(dir_acc, 1),
        "mape":         round(mape, 2),
        "win_rate":     round(win_rate, 1),
        "trades":       trades,
        "n_test":       len(preds),
        "train_size":   train_size,
    }

# ─────────────────────────────────────────────
#  INTRADAY MODEL  (MLP Neural Net)
# ─────────────────────────────────────────────
def build_intraday_model(intra_df, target):
    df = intra_df.copy()
    df['RSI']        = compute_rsi(df[target], period=7)
    df['MA_5']       = df[target].rolling(5).mean()
    df['MA_15']      = df[target].rolling(15).mean()
    df['MACD'], df['Sig'] = compute_macd(df[target], fast=6, slow=13, signal=5)
    df['Return']     = df[target].pct_change()
    df['Volatility'] = df[target].rolling(5).std()
    df['Target']     = df[target].shift(-1)

    feat = [target, 'RSI', 'MA_5', 'MA_15', 'MACD', 'Sig', 'Return', 'Volatility']
    df = df.dropna(subset=feat + ['Target']).copy()
    if len(df) < 20:
        return None, None, None, None

    scaler = StandardScaler()
    X = scaler.fit_transform(df[feat])
    y = df['Target'].values

    model = MLPRegressor(
        hidden_layer_sizes=(128, 64, 32),
        activation='relu',
        max_iter=500,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1
    )
    model.fit(X, y)
    return model, scaler, df, feat

# ─────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────
if 'intraday_history' not in st.session_state:
    st.session_state.intraday_history = {}
if 'monthly_history' not in st.session_state:
    st.session_state.monthly_history = {}
if 'last_ticker' not in st.session_state:
    st.session_state.last_ticker = None
# Per-stock model store: key=ticker, value={xgb_model, scaler, feature_cols, trained_on, params}
if 'trained_models' not in st.session_state:
    st.session_state.trained_models = {}

# ─────────────────────────────────────────────
#  PSX STOCKS LIST
# ─────────────────────────────────────────────
PSX_STOCKS = {
    "--- INDEX ---": {"KSE-100 Index": "^KSE"},
    "--- OIL & GAS ---": {
        "OGDC": "OGDC.KA", "PPL (Pak Petroleum)": "PPL.KA",
        "PSO (Pak State Oil)": "PSO.KA", "MARI Petroleum": "MARI.KA",
    },
    "--- BANKING ---": {
        "HBL (Habib Bank)": "HBL.KA", "UBL (United Bank)": "UBL.KA",
        "MCB Bank": "MCB.KA", "Bank Al-Habib": "BAHL.KA",
        "Meezan Bank": "MEBL.KA", "NBP (National Bank)": "NBP.KA",
    },
    "--- FERTILIZER ---": {
        "Engro Fertilizers": "EFERT.KA", "Fauji Fertilizer": "FFC.KA",
        "Fauji Fert Bin Qasim": "FFBL.KA",
    },
    "--- CEMENT ---": {
        "Lucky Cement": "LUCK.KA", "DG Khan Cement": "DGKC.KA",
        "Maple Leaf Cement": "MLCF.KA", "Bestway Cement": "BWCL.KA",
    },
    "--- POWER ---": {
        "Hub Power (HUBCO)": "HUBC.KA", "Kot Addu Power (KAPCO)": "KAPCO.KA",
    },
    "--- TELECOM ---": {
        "Pakistan Telecom (PTCL)": "PTC.KA", "TRG Pakistan": "TRG.KA",
        "Systems Ltd": "SYS.KA",
    },
    "--- TEXTILE ---": {"Nishat Mills": "NML.KA", "Interloop": "ILP.KA"},
    "--- COMMODITIES (GLOBAL) ---": {
        "Gold Futures": "GC=F", "Silver Futures": "SI=F", "Crude Oil": "CL=F",
    }
}

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.title("🦅 AI Market Oracle Pro")
st.sidebar.markdown("---")

now_pkt = pkt_now()
st.sidebar.markdown(f"""
<div class="clock-box">
🕐 Pakistan Time (UTC+5)<br>
<b>{now_pkt.strftime('%A, %d %b %Y')}</b><br>
{now_pkt.strftime('%H:%M:%S')} PKT
</div>
""", unsafe_allow_html=True)

psx_open  = now_pkt.replace(hour=9,  minute=30, second=0, microsecond=0)
psx_close = now_pkt.replace(hour=15, minute=30, second=0, microsecond=0)
if psx_open <= now_pkt <= psx_close and now_pkt.weekday() < 5:
    st.sidebar.success("🟢 PSX Market OPEN")
else:
    st.sidebar.error("🔴 PSX Market CLOSED")

st.sidebar.markdown("---")

source = st.sidebar.radio("📡 Data Source:",
    ["Yahoo Finance (Live)", "Alpha Vantage API", "File Upload"])

main_df, target, selected_name, ticker = None, None, "", ""

# ─── Yahoo Finance ───────────────────────────
if source == "Yahoo Finance (Live)":
    st.sidebar.markdown("### 📊 Market Select Karein")
    category = st.sidebar.selectbox("Category:", list(PSX_STOCKS.keys()))
    stocks_in_cat = PSX_STOCKS[category]
    selected_name = st.sidebar.selectbox("Stock/Index:", list(stocks_in_cat.keys()))
    ticker = stocks_in_cat[selected_name]

    period_map = {"6 Mahine": "6mo", "1 Saal": "1y", "2 Saal": "2y", "5 Saal": "5y"}
    period_label = st.sidebar.selectbox("Data Period:", list(period_map.keys()), index=2)
    period = period_map[period_label]

    st.sidebar.markdown("**Ya apna ticker dalein:**")
    custom_ticker = st.sidebar.text_input("Custom Ticker (e.g. ENGRO.KA)", value="")
    if custom_ticker.strip():
        ticker = custom_ticker.strip()
        selected_name = ticker

    col1, col2 = st.sidebar.columns(2)
    fetch_btn   = col1.button("🔄 Fetch",    use_container_width=True)
    refresh_btn = col2.button("♻️ Refresh",  use_container_width=True)

    if refresh_btn:
        st.cache_data.clear()
        st.sidebar.success("Cache clear!")

    if fetch_btn or refresh_btn:
        with st.sidebar:
            with st.spinner(f"Fetching {selected_name}..."):
                raw, err = fetch_live_data(ticker, period)
                if err:
                    st.error(f"Error: {err}")
                elif raw is not None:
                    main_df, target = deep_clean_data(raw)
                    if main_df is not None:
                        st.success(f"✅ {len(main_df)} rows mili!")

    st.sidebar.info("⏱️ 5 min cache. Refresh = live update.")

    # ── Model Training Section ────────────────
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🤖 Model Training")

    # Current model status for this ticker
    _tm = st.session_state.trained_models.get(ticker)
    if _tm:
        st.sidebar.success(
            f"✅ **{ticker}** trained\n\n"
            f"📅 {_tm['trained_on']}\n\n"
            f"📊 {_tm['n_rows']} rows | "
            f"🌲 {_tm['params']['n_estimators']} trees"
        )
    else:
        st.sidebar.warning(f"⚠️ **{ticker}** — model nahi hai. Neeche train karein.")

    with st.sidebar.expander("⚙️ XGBoost Hyperparameters", expanded=False):
        sb_n_est   = st.slider("Trees (n_estimators)",    50,  500, 300, step=50)
        sb_lr      = st.slider("Learning Rate",          0.01, 0.2, 0.04, step=0.01)
        sb_depth   = st.slider("Max Depth",               2,   10,   5,  step=1)
        sb_subsamp = st.slider("Subsample",              0.5,  1.0, 0.8, step=0.1)
        sb_colsamp = st.slider("ColSample ByTree",       0.5,  1.0, 0.8, step=0.1)

    with st.sidebar.expander("⚙️ MLP (Intraday) Hyperparameters", expanded=False):
        sb_mlp_l1  = st.slider("Layer 1 Neurons",  32, 256, 128, step=32)
        sb_mlp_l2  = st.slider("Layer 2 Neurons",  16, 128,  64, step=16)
        sb_mlp_l3  = st.slider("Layer 3 Neurons",   8,  64,  32, step=8)
        sb_mlp_iter= st.slider("Max Iterations",  100, 1000, 500, step=100)

    train_col1, train_col2 = st.sidebar.columns(2)
    train_btn  = train_col1.button("🚀 Train Model",   use_container_width=True, key="train_btn")
    delete_btn = train_col2.button("🗑️ Delete Model",  use_container_width=True, key="del_btn")

    if delete_btn and ticker in st.session_state.trained_models:
        del st.session_state.trained_models[ticker]
        st.sidebar.success(f"🗑️ {ticker} model delete ho gaya!")
        st.rerun()

    if train_btn:
        if main_df is not None and target is not None:
            with st.sidebar:
                with st.spinner(f"🚀 {ticker} model training..."):
                    _df_tr = main_df.copy()
                    _df_tr['RSI']        = compute_rsi(_df_tr[target], period=14)
                    _df_tr['MA_10']      = _df_tr[target].rolling(10).mean()
                    _df_tr['MA_20']      = _df_tr[target].rolling(20).mean()
                    _df_tr['Volatility'] = _df_tr[target].rolling(10).std()
                    _df_tr['MACD'], _df_tr['Signal'] = compute_macd(_df_tr[target])
                    _df_tr['Return']     = _df_tr[target].pct_change()
                    _df_tr['Target']     = _df_tr[target].shift(-1)
                    _feat = [target,'RSI','MA_10','MA_20','Volatility','MACD','Signal','Return']
                    _df_tr = _df_tr.dropna(subset=_feat+['Target']).copy()

                    if len(_df_tr) >= 15:
                        _sc = StandardScaler()
                        _X  = _sc.fit_transform(_df_tr[_feat])
                        _y  = _df_tr['Target'].values
                        _params = dict(
                            n_estimators=sb_n_est, learning_rate=sb_lr,
                            max_depth=sb_depth, subsample=sb_subsamp,
                            colsample_bytree=sb_colsamp, random_state=42, verbosity=0
                        )
                        _mdl = xgb.XGBRegressor(**_params)
                        _mdl.fit(_X, _y)
                        st.session_state.trained_models[ticker] = {
                            'xgb_model':    _mdl,
                            'scaler':       _sc,
                            'feature_cols': _feat,
                            'trained_on':   now_pkt.strftime('%d %b %Y %H:%M'),
                            'n_rows':       len(_df_tr),
                            'params':       _params,
                            'mlp_params':   dict(
                                hidden_layer_sizes=(sb_mlp_l1, sb_mlp_l2, sb_mlp_l3),
                                max_iter=sb_mlp_iter
                            ),
                        }
                        st.sidebar.success(f"✅ {ticker} model ready! ({len(_df_tr)} rows)")
                        st.rerun()
                    else:
                        st.sidebar.error("Kafi data nahi — pehle Fetch karein!")
        else:
            st.sidebar.error("Pehle data Fetch karein, phir Train karein!")

    # Show all trained models
    if st.session_state.trained_models:
        with st.sidebar.expander(f"📦 Trained Models ({len(st.session_state.trained_models)})", expanded=False):
            for _tk, _info in st.session_state.trained_models.items():
                st.markdown(
                    f"**{_tk}** — {_info['n_rows']} rows | {_info['trained_on']}"
                )
            if st.button("🗑️ Delete ALL Models", key="del_all"):
                st.session_state.trained_models = {}
                st.rerun()

# ─── Alpha Vantage ───────────────────────────
elif source == "Alpha Vantage API":
    st.sidebar.info("Free API key: alphavantage.co")
    key = st.sidebar.text_input("API Key:", type="password")
    av_symbol = st.sidebar.text_input("Symbol (e.g. IBM):", value="IBM")
    if st.sidebar.button("Fetch API Data"):
        if key:
            try:
                url = (f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY'
                       f'&symbol={av_symbol}&apikey={key}&outputsize=full')
                r = requests.get(url, timeout=15).json()
                data_key = next((k for k in r if "Time Series" in k), None)
                if data_key:
                    raw_df = pd.DataFrame.from_dict(r[data_key], orient='index')
                    main_df, target = deep_clean_data(raw_df)
                    selected_name = av_symbol
                    ticker = av_symbol
                    if main_df is not None:
                        st.sidebar.success(f"✅ {len(main_df)} rows!")
                else:
                    st.sidebar.error(f"Response keys: {list(r.keys())[:3]}")
            except Exception as e:
                st.sidebar.error(f"Network Error: {e}")
        else:
            st.sidebar.warning("Pehle API key dalein!")

# ─── File Upload ─────────────────────────────
elif source == "File Upload":
    st.sidebar.info("CSV mein Date aur Close column hona chahiye")
    file = st.file_uploader("CSV Upload Karein", type="csv")
    if file:
        main_df, target = deep_clean_data(pd.read_csv(file))
        selected_name = file.name
        ticker = file.name
        if main_df is not None:
            st.sidebar.success(f"✅ {len(main_df)} rows!")

# ═════════════════════════════════════════════
#  MAIN DASHBOARD
# ═════════════════════════════════════════════
if main_df is not None and target is not None:
    try:
        # ── Feature Engineering ──
        df = main_df.copy()
        df['RSI']        = compute_rsi(df[target], period=14)
        df['MA_10']      = df[target].rolling(10).mean()
        df['MA_20']      = df[target].rolling(20).mean()
        df['Volatility'] = df[target].rolling(10).std()
        df['MACD'], df['Signal'] = compute_macd(df[target])
        df['Return']     = df[target].pct_change()
        df['Target']     = df[target].shift(-1)

        feature_cols = [target, 'RSI', 'MA_10', 'MA_20', 'Volatility', 'MACD', 'Signal', 'Return']
        clean_df = df.dropna(subset=feature_cols + ['Target']).copy()

        if len(clean_df) < 15:
            st.error(f"Sirf {len(clean_df)} rows hain — 15+ chahiye.")
            st.stop()

        # ── Use saved model if available, else train with defaults ──
        _saved = st.session_state.trained_models.get(ticker)
        if _saved:
            # Saved model use karo
            scaler       = _saved['scaler']
            xgb_model    = _saved['xgb_model']
            feature_cols = _saved['feature_cols']
            X = scaler.transform(clean_df[feature_cols])
            y = clean_df['Target'].values
            _model_src = f"💾 Saved Model ({_saved['trained_on']})"
        else:
            # Default training (auto)
            scaler = StandardScaler()
            X = scaler.fit_transform(clean_df[feature_cols])
            y = clean_df['Target'].values
            xgb_model = xgb.XGBRegressor(
                n_estimators=300, learning_rate=0.04,
                max_depth=5, subsample=0.8,
                colsample_bytree=0.8, random_state=42, verbosity=0
            )
            xgb_model.fit(X, y)
            _model_src = "⚡ Auto-Trained (Default)"  

        curr      = float(clean_df[target].iloc[-1])
        pred_next = float(xgb_model.predict(X[[-1]])[0])
        rsi_now   = float(clean_df['RSI'].iloc[-1])
        delta     = pred_next - curr
        delta_pct = (delta / curr) * 100

        if delta_pct > 1:
            signal_txt, signal_cls = "📈 BUY",  "buy"
        elif delta_pct < -1:
            signal_txt, signal_cls = "📉 SELL", "sell"
        else:
            signal_txt, signal_cls = "⚖️ HOLD", "hold"

        bt = run_backtest(clean_df, target, feature_cols, scaler, xgb_model)

        # ── 30-Day Forecast ──
        monthly_path = [curr]
        step30 = (pred_next - curr) / 30
        np.random.seed(42)
        for _ in range(30):
            noise = np.random.normal(0, abs(curr) * 0.002)
            monthly_path.append(monthly_path[-1] + step30 + noise)

        last_date = clean_df['Date'].iloc[-1]
        future_dates_30 = [last_date + timedelta(days=i) for i in range(31)]

        # ── Intraday Model ──
        # FIX: initialize all intraday variables with safe defaults BEFORE the block
        intraday_ok   = False
        intra_curr    = curr
        intra_path    = []
        intra_times   = []
        intra_dir_acc = 0.0
        intra_mape    = 0.0
        intra_clean   = None          # FIX: defined here so Tab 3 never crashes
        intra_target  = target

        intra_raw, intra_err = fetch_intraday_data(ticker)

        if intra_raw is not None and not intra_err:
            intra_df_raw, _intra_target = deep_clean_data(intra_raw)
            if intra_df_raw is not None and len(intra_df_raw) > 30:
                mlp_model, mlp_scaler, _intra_clean, intra_feats = build_intraday_model(
                    intra_df_raw, _intra_target
                )
                if mlp_model is not None:
                    # Override MLP with saved params if available
                    _mlp_params = (_saved or {}).get('mlp_params', {})
                    if _mlp_params:
                        _hl = _mlp_params.get('hidden_layer_sizes', (128,64,32))
                        _mi = _mlp_params.get('max_iter', 500)
                        _new_mlp = MLPRegressor(
                            hidden_layer_sizes=_hl, activation='relu',
                            max_iter=_mi, random_state=42,
                            early_stopping=True, validation_fraction=0.1
                        )
                        from sklearn.preprocessing import StandardScaler as _SC
                        _new_sc = _SC()
                        _Xr = _new_sc.fit_transform(intra_clean[intra_feats])
                        _yr = intra_clean['Target'].values
                        _new_mlp.fit(_Xr, _yr)
                        mlp_model  = _new_mlp
                        mlp_scaler = _new_sc
                    intraday_ok  = True
                    intra_target = _intra_target
                    intra_clean  = _intra_clean
                    intra_curr   = float(intra_clean[intra_target].iloc[-1])

                    n_steps = 96
                    intra_path = [intra_curr]

                    last_intra_t = intra_clean['Date'].iloc[-1]
                    if last_intra_t.tzinfo is None:
                        last_intra_t = pytz.utc.localize(last_intra_t).astimezone(PKT)
                    else:
                        last_intra_t = last_intra_t.astimezone(PKT)

                    intra_times = [last_intra_t + timedelta(minutes=5 * i) for i in range(n_steps + 1)]

                    X_last_intra = mlp_scaler.transform(intra_clean[intra_feats].iloc[[-1]])
                    pred_step    = float(mlp_model.predict(X_last_intra)[0])
                    intra_step   = (pred_step - intra_curr) / n_steps

                    np.random.seed(int(now_pkt.timestamp()) // 300)
                    for _ in range(n_steps):
                        noise = np.random.normal(0, abs(intra_curr) * 0.0008)
                        intra_path.append(intra_path[-1] + intra_step + noise)

                    # Intraday backtest
                    n_intra  = len(intra_clean)
                    tr_intra = int(n_intra * 0.7)
                    X_intra_all  = mlp_scaler.transform(intra_clean[intra_feats])
                    preds_intra  = mlp_model.predict(X_intra_all[tr_intra:])
                    acts_intra   = intra_clean['Target'].values[tr_intra:]
                    prev_intra   = intra_clean[intra_target].values[tr_intra:]

                    intra_dir = sum(
                        1 for p, a, pv in zip(preds_intra, acts_intra, prev_intra)
                        if (p > pv) == (a > pv)
                    )
                    intra_dir_acc = round(intra_dir / len(preds_intra) * 100, 1) if len(preds_intra) > 0 else 0
                    try:
                        intra_mape = round(mean_absolute_percentage_error(acts_intra, preds_intra) * 100, 2)
                    except Exception:
                        intra_mape = 0.0

        # ── Session State Update ──
        if ticker != st.session_state.last_ticker:
            st.session_state.intraday_history[ticker] = []
            st.session_state.monthly_history[ticker]  = []
            st.session_state.last_ticker = ticker

        if intraday_ok:
            ih = st.session_state.intraday_history.setdefault(ticker, [])
            if not ih or (now_pkt - ih[-1]['time']).total_seconds() >= 300:
                ih.append({'time': now_pkt, 'price': intra_curr})
                if len(ih) > 96:
                    ih.pop(0)

        mh = st.session_state.monthly_history.setdefault(ticker, [])
        if not mh or (now_pkt - mh[-1]['time']).total_seconds() >= 3600:
            mh.append({'time': now_pkt, 'price': curr, 'pred': pred_next})
            if len(mh) > 24 * 30:
                mh.pop(0)

        # ═══════════════════════ UI ═══════════════════════
        st.markdown("# 🦅 AI Market Oracle Pro")
        st.markdown(f"### {selected_name}")
        st.caption(
            f"🕐 **PKT:** {now_pkt.strftime('%d %b %Y  %H:%M:%S')}  |  "
            f"🌐 **UTC:** {datetime.utcnow().strftime('%H:%M:%S')}  |  "
            f"Source: {source}  |  Model: {_model_src}"
        )
        st.markdown("---")

        # ── Metrics ──
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("💰 Current Price",   f"{curr:,.2f}")
        c2.metric("🤖 XGB Prediction",  f"{pred_next:,.2f}",
                  f"{delta:+.2f} ({delta_pct:+.2f}%)")
        c3.metric("📊 RSI (14)",         f"{rsi_now:.1f}",
                  "Overbought" if rsi_now > 70 else ("Oversold" if rsi_now < 30 else "Neutral"))
        c4.metric("📋 Data Points",      f"{len(clean_df):,}")
        c5.metric("🎯 Signal",           signal_txt)
        if intraday_ok:
            c6.metric("⚡ Intraday",     f"{intra_curr:,.2f}")
        st.markdown("---")

        # ═══════════════ TABS ═════════════════════════════
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📈 Historical",
            "📅 Monthly Forecast",
            "⚡ Intraday Forecast",
            "📉 Indicators",
            "📊 Candlestick",
            "🧪 Backtesting"
        ])

        # ─── TAB 1: Historical ────────────────────────────
        with tab1:
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Scatter(
                x=clean_df['Date'], y=clean_df[target],
                mode='lines', name='Close Price',
                line=dict(color='#00bcd4', width=1.5)
            ))
            fig_hist.add_trace(go.Scatter(
                x=clean_df['Date'], y=clean_df['MA_10'],
                mode='lines', name='MA 10',
                line=dict(color='#ff9800', width=1, dash='dot')
            ))
            fig_hist.add_trace(go.Scatter(
                x=clean_df['Date'], y=clean_df['MA_20'],
                mode='lines', name='MA 20',
                line=dict(color='#e040fb', width=1, dash='dot')
            ))
            fig_hist.update_layout(
                title=f"{selected_name} — Historical Close Price",
                template="plotly_dark", xaxis_title="Date (PKT)", yaxis_title="Price",
                hovermode="x unified", height=450,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(13,21,38,0.8)'
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        # ─── TAB 2: Monthly Forecast ──────────────────────
        with tab2:
            fig_month = go.Figure()
            last60 = clean_df.tail(60)
            fig_month.add_trace(go.Scatter(
                x=last60['Date'], y=last60[target],
                mode='lines', name='Historical (60d)',
                line=dict(color='#00bcd4', width=1.8)
            ))

            mh = st.session_state.monthly_history.get(ticker, [])
            if len(mh) > 1:
                fig_month.add_trace(go.Scatter(
                    x=[e['time'] for e in mh],
                    y=[e['price'] for e in mh],
                    mode='lines+markers', name='Live Actual',
                    line=dict(color='#00e676', width=2),
                    marker=dict(size=5)
                ))

            upper30 = [p + abs(curr) * 0.015 * (i + 1) ** 0.4 for i, p in enumerate(monthly_path)]
            lower30 = [p - abs(curr) * 0.015 * (i + 1) ** 0.4 for i, p in enumerate(monthly_path)]

            fig_month.add_trace(go.Scatter(
                x=future_dates_30 + future_dates_30[::-1],
                y=upper30 + lower30[::-1],
                fill='toself', fillcolor='rgba(255,152,0,0.08)',
                line=dict(color='rgba(255,152,0,0)'),
                name='Confidence Band'
            ))
            fig_month.add_trace(go.Scatter(
                x=future_dates_30, y=monthly_path,
                mode='lines', name='XGBoost Forecast (30d)',
                line=dict(color='#ff9800', width=2.5, dash='dash')
            ))
            # FIX: use numeric unix ms — most reliable across Plotly versions
            fig_month.add_vline(
                x=pd.Timestamp(last_date).value // 10**6,
                line_dash="dash", line_color="#607d8b",
                annotation_text="Today"
            )
            fig_month.update_layout(
                title=f"📅 30-Day XGBoost Forecast — {selected_name}",
                template="plotly_dark", xaxis_title="Date", yaxis_title="Price",
                hovermode="x unified", height=470,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(13,21,38,0.8)'
            )
            st.plotly_chart(fig_month, use_container_width=True)

            ca, cb = st.columns(2)
            ca.info(f"**Next Day Prediction (XGBoost):** {pred_next:,.2f}")
            cb.markdown(
                f"**Signal:** <span class='signal-badge {signal_cls}'>{signal_txt}</span>",
                unsafe_allow_html=True
            )

        # ─── TAB 3: Intraday Forecast ─────────────────────
        with tab3:
            if not intraday_ok:
                st.warning(
                    "Intraday data nahi mila. Yahoo Finance se 5-min data chahiye. "
                    "PSX stocks ke liye availability limited hai."
                )
            else:
                fig_intra = go.Figure()

                ih = st.session_state.intraday_history.get(ticker, [])
                if len(ih) > 1:
                    fig_intra.add_trace(go.Scatter(
                        x=[e['time'] for e in ih],
                        y=[e['price'] for e in ih],
                        mode='lines+markers', name='Actual (Live)',
                        line=dict(color='#00bcd4', width=2),
                        marker=dict(size=4, color='#00e5ff')
                    ))
                else:
                    # FIX: intra_clean is guaranteed to be set when intraday_ok=True
                    tail_intra = intra_clean.tail(24)
                    dates_pkt = [
                        pytz.utc.localize(d).astimezone(PKT) if d.tzinfo is None
                        else d.astimezone(PKT)
                        for d in tail_intra['Date']
                    ]
                    fig_intra.add_trace(go.Scatter(
                        x=dates_pkt, y=tail_intra[intra_target],
                        mode='lines', name='Last 2 Hours',
                        line=dict(color='#00bcd4', width=2)
                    ))

                upper_i = [p + abs(intra_curr) * 0.005 * (i + 1) ** 0.3 for i, p in enumerate(intra_path)]
                lower_i = [p - abs(intra_curr) * 0.005 * (i + 1) ** 0.3 for i, p in enumerate(intra_path)]

                fig_intra.add_trace(go.Scatter(
                    x=intra_times + intra_times[::-1],
                    y=upper_i + lower_i[::-1],
                    fill='toself', fillcolor='rgba(100,255,218,0.06)',
                    line=dict(color='rgba(0,0,0,0)'),
                    name='Confidence Band'
                ))
                fig_intra.add_trace(go.Scatter(
                    x=intra_times, y=intra_path,
                    mode='lines', name='MLP Neural Net Forecast (8h)',
                    line=dict(color='#64ffda', width=2.5, dash='dash')
                ))
                # FIX: vline string format
                fig_intra.add_vline(
                    x=int(now_pkt.timestamp() * 1000),
                    line_dash="dash", line_color="#78909c",
                    annotation_text="Now (PKT)"
                )
                fig_intra.update_layout(
                    title=f"⚡ 8-Hour MLP Neural Net Forecast — {selected_name}",
                    template="plotly_dark",
                    xaxis_title="Time (Pakistan Standard Time, UTC+5)",
                    yaxis_title="Price",
                    hovermode="x unified", height=470,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(13,21,38,0.8)'
                )
                st.plotly_chart(fig_intra, use_container_width=True)

                ci1, ci2, ci3 = st.columns(3)
                ci1.metric("⚡ Intraday Current",   f"{intra_curr:,.2f}")
                ci2.metric("🔮 8h MLP Prediction",  f"{intra_path[-1]:,.2f}",
                           f"{intra_path[-1] - intra_curr:+.2f}")
                ci3.metric("🎯 MLP Direction Acc",  f"{intra_dir_acc}%")

                st.info(
                    "ℹ️ **Graph persistent hai** — har refresh pe sirf naye 5-min data points "
                    "add hote hain. Graph reset nahi hota jab tak aap stock na badlein."
                )

        # ─── TAB 4: Indicators ────────────────────────────
        with tab4:
            col_r, col_m = st.columns(2)
            with col_r:
                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(
                    x=clean_df['Date'], y=clean_df['RSI'],
                    mode='lines', name='RSI',
                    line=dict(color='#e040fb', width=1.5)
                ))
                fig_rsi.add_hrect(y0=70, y1=100, fillcolor="rgba(255,23,68,0.07)",   line_width=0)
                fig_rsi.add_hrect(y0=0,  y1=30,  fillcolor="rgba(0,200,83,0.07)",    line_width=0)
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="#ff1744",
                                  annotation_text="Overbought (70)")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="#00c853",
                                  annotation_text="Oversold (30)")
                fig_rsi.update_layout(
                    title="RSI (14)", template="plotly_dark",
                    yaxis=dict(range=[0, 100]), height=300,
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_rsi, use_container_width=True)

            with col_m:
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Scatter(
                    x=clean_df['Date'], y=clean_df['MACD'],
                    mode='lines', name='MACD',
                    line=dict(color='#00bcd4', width=1.5)
                ))
                fig_macd.add_trace(go.Scatter(
                    x=clean_df['Date'], y=clean_df['Signal'],
                    mode='lines', name='Signal',
                    line=dict(color='#ff9800', width=1.5)
                ))
                hist_macd    = clean_df['MACD'] - clean_df['Signal']
                colors_macd  = ['#00c853' if v >= 0 else '#ff1744' for v in hist_macd]
                fig_macd.add_trace(go.Bar(
                    x=clean_df['Date'], y=hist_macd,
                    name='Histogram', marker_color=colors_macd, opacity=0.5
                ))
                fig_macd.add_hline(y=0, line_color='gray', line_dash='dot')
                fig_macd.update_layout(
                    title="MACD (12/26/9)", template="plotly_dark",
                    height=300, paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_macd, use_container_width=True)

            fig_vol = go.Figure()
            fig_vol.add_trace(go.Scatter(
                x=clean_df['Date'], y=clean_df['Volatility'],
                mode='lines', fill='tozeroy', name='Volatility',
                line=dict(color='#ff9800'),
                fillcolor='rgba(255,152,0,0.12)'
            ))
            fig_vol.update_layout(
                title="Rolling Volatility (10-day)", template="plotly_dark",
                height=250, paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_vol, use_container_width=True)

        # ─── TAB 5: Candlestick ───────────────────────────
        with tab5:
            ohlc_ok = all(c.title() in df.columns for c in ['Open', 'High', 'Low', 'Close'])
            if ohlc_ok:
                candle_df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Date']).tail(120)
                fig_c = go.Figure(data=[go.Candlestick(
                    x=candle_df['Date'],
                    open=candle_df['Open'], high=candle_df['High'],
                    low=candle_df['Low'],   close=candle_df['Close'],
                    increasing_line_color='#00c853',
                    decreasing_line_color='#ff1744',
                    name='OHLC'
                )])
                if 'Volume' in candle_df.columns:
                    fig_c.add_trace(go.Bar(
                        x=candle_df['Date'], y=candle_df['Volume'],
                        name='Volume', yaxis='y2',
                        marker_color='rgba(100,180,255,0.25)'
                    ))
                    fig_c.update_layout(
                        yaxis2=dict(overlaying='y', side='right',
                                    showgrid=False, showticklabels=False)
                    )
                fig_c.update_layout(
                    title=f"{selected_name} — Candlestick (Last 120 Days)",
                    template="plotly_dark", xaxis_title="Date", yaxis_title="Price",
                    xaxis_rangeslider_visible=False, height=520,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(13,21,38,0.8)'
                )
                st.plotly_chart(fig_c, use_container_width=True)
            else:
                st.warning("Candlestick ke liye OHLC columns chahiye (Yahoo Finance).")

        # ─── TAB 6: Backtesting ───────────────────────────
        with tab6:
            st.markdown("## 🧪 Backtesting Report")
            st.markdown(f"**Model:** XGBoost (Daily/Monthly) | **Stock:** {selected_name}")
            st.markdown("---")

            def acc_cls(v, good=60, ok=50):
                if v >= good: return "bt-good"
                elif v >= ok: return "bt-ok"
                return "bt-bad"

            def mape_cls(v):
                if v <= 2:   return "bt-good"
                elif v <= 5: return "bt-ok"
                return "bt-bad"

            if bt:
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    cls = acc_cls(bt['dir_accuracy'])
                    st.markdown(f"""
                    <div class="bt-card">
                        <div style="font-size:13px;color:#7a9cc4;">🎯 Direction Accuracy</div>
                        <div class="{cls}" style="font-size:28px;">{bt['dir_accuracy']}%</div>
                        <div style="font-size:12px;color:#546e8a;">
                        Kitni baar sahi direction | Test: {bt['n_test']} days
                        </div>
                    </div>""", unsafe_allow_html=True)

                with col_b2:
                    cls = mape_cls(bt['mape'])
                    st.markdown(f"""
                    <div class="bt-card">
                        <div style="font-size:13px;color:#7a9cc4;">📐 MAPE (Price Error)</div>
                        <div class="{cls}" style="font-size:28px;">{bt['mape']}%</div>
                        <div style="font-size:12px;color:#546e8a;">
                        ≤2% Excellent | ≤5% OK | >5% High
                        </div>
                    </div>""", unsafe_allow_html=True)

                with col_b3:
                    cls = acc_cls(bt['win_rate'])
                    st.markdown(f"""
                    <div class="bt-card">
                        <div style="font-size:13px;color:#7a9cc4;">💹 Trade Win Rate</div>
                        <div class="{cls}" style="font-size:28px;">{bt['win_rate']}%</div>
                        <div style="font-size:12px;color:#546e8a;">
                        BUY/SELL signals mein profitable | Signals: {sum(bt['trades'].values())}
                        </div>
                    </div>""", unsafe_allow_html=True)

                st.markdown("### 📊 Trade Breakdown")
                t = bt['trades']
                tot_buy  = t['buy_win']  + t['buy_loss']
                tot_sell = t['sell_win'] + t['sell_loss']
                buy_wr   = round(t['buy_win']  / tot_buy  * 100, 1) if tot_buy  > 0 else 0
                sell_wr  = round(t['sell_win'] / tot_sell * 100, 1) if tot_sell > 0 else 0

                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.markdown(f"""
                    <div class="bt-card">
                        <div style="font-size:14px;color:#00c853;font-weight:700;">📈 BUY Signals</div>
                        <div style="margin-top:8px;">
                        ✅ Win: <b>{t['buy_win']}</b> &nbsp;|&nbsp; ❌ Loss: <b>{t['buy_loss']}</b><br>
                        Win Rate: <span class="{acc_cls(buy_wr)}">{buy_wr}%</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
                with col_t2:
                    st.markdown(f"""
                    <div class="bt-card">
                        <div style="font-size:14px;color:#ff1744;font-weight:700;">📉 SELL Signals</div>
                        <div style="margin-top:8px;">
                        ✅ Win: <b>{t['sell_win']}</b> &nbsp;|&nbsp; ❌ Loss: <b>{t['sell_loss']}</b><br>
                        Win Rate: <span class="{acc_cls(sell_wr)}">{sell_wr}%</span>
                        </div>
                    </div>""", unsafe_allow_html=True)

                # Actual vs Predicted chart
                st.markdown("### 📈 Actual vs Predicted (Test Period)")
                train_sz   = bt['train_size']
                test_df    = clean_df.iloc[train_sz:].copy()
                X_test     = scaler.transform(test_df[feature_cols])
                test_preds = xgb_model.predict(X_test)

                fig_bt = go.Figure()
                fig_bt.add_trace(go.Scatter(
                    x=test_df['Date'], y=test_df[target],
                    mode='lines', name='Actual',
                    line=dict(color='#00bcd4', width=1.5)
                ))
                fig_bt.add_trace(go.Scatter(
                    x=test_df['Date'], y=test_preds,
                    mode='lines', name='XGB Predicted',
                    line=dict(color='#ff9800', width=1.5, dash='dot')
                ))
                fig_bt.update_layout(
                    title="Backtest: Actual vs XGBoost Predicted",
                    template="plotly_dark", xaxis_title="Date", yaxis_title="Price",
                    hovermode="x unified", height=380,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(13,21,38,0.8)'
                )
                st.plotly_chart(fig_bt, use_container_width=True)

                # Intraday backtest section
                if intraday_ok:
                    st.markdown("---")
                    st.markdown("### ⚡ Intraday MLP Model Backtest")
                    col_ib1, col_ib2 = st.columns(2)
                    with col_ib1:
                        cls = acc_cls(intra_dir_acc)
                        st.markdown(f"""
                        <div class="bt-card">
                            <div style="font-size:13px;color:#7a9cc4;">🎯 MLP Direction Accuracy</div>
                            <div class="{cls}" style="font-size:28px;">{intra_dir_acc}%</div>
                            <div style="font-size:12px;color:#546e8a;">5-min intraday test set</div>
                        </div>""", unsafe_allow_html=True)
                    with col_ib2:
                        cls = mape_cls(intra_mape)
                        st.markdown(f"""
                        <div class="bt-card">
                            <div style="font-size:13px;color:#7a9cc4;">📐 MLP MAPE</div>
                            <div class="{cls}" style="font-size:28px;">{intra_mape}%</div>
                            <div style="font-size:12px;color:#546e8a;">Price prediction error</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("---")
                st.markdown("""
                <div style="background:#0d1526;border:1px solid #1e3a5f;border-radius:10px;
                            padding:14px 18px;font-size:13px;color:#7a9cc4;">
                ⚠️ <b>Disclaimer:</b> Yeh backtest results sirf educational purposes ke liye hain.
                Past performance future results ki guarantee nahi. Investment decisions ke liye
                professional financial advisor se consult karein.
                </div>""", unsafe_allow_html=True)
            else:
                st.warning("Backtest ke liye kafi data nahi (minimum 30 data points chahiye).")

    except Exception as e:
        st.error(f"Logic Error: {e}")
        st.exception(e)

# ─── Welcome Screen ────────────────────────────────
else:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;">
        <h1 style="font-family:'Orbitron',monospace;color:#00bcd4;font-size:2.5rem;">
            🦅 AI Market Oracle Pro
        </h1>
        <p style="color:#546e8a;font-size:1.1rem;margin-top:10px;">
            Professional AI-Powered Stock Market Analysis — Pakistan Stock Exchange
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.info("👈 Sidebar se **Yahoo Finance** select karein, stock choose karein, phir **Fetch** karein.")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("""
        ### 📋 Features
        - ✅ KSE-100 + PSX Stocks live data
        - ✅ Pakistan Time (UTC+5) display
        - ✅ Gold, Silver, Crude Oil futures
        - ✅ **XGBoost** — 30-day monthly forecast
        - ✅ **MLP Neural Net** — 8-hour intraday forecast
        - ✅ RSI + MACD (with histogram) + Volatility
        - ✅ Candlestick with Volume
        - ✅ 5-min cache, Refresh = live update
        """)
    with col_f2:
        st.markdown("""
        ### 🧪 Backtesting
        - ✅ Walk-forward backtest (70/30 split)
        - ✅ Direction Accuracy %
        - ✅ MAPE (Price Error %)
        - ✅ Trade Win Rate %
        - ✅ BUY / SELL signal breakdown
        - ✅ Actual vs Predicted chart
        - ✅ Intraday MLP separate backtest

        ### 📊 Persistent Graphs
        - ✅ Intraday graph refresh pe accumulate hota hai
        - ✅ Monthly graph refresh pe accumulate hota hai
        - ✅ New stock select = fresh start
        """)