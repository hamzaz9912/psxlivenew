"""Patch script: Replace Chart 1 (1H forecast) with enhanced candlestick chart."""

NEW_BLOCK = """\
            # ══════════════════════════════════════════════════════════════════
            # CHART 1 — 1-HOUR FORECAST: ENHANCED CANDLESTICK + TECHNICALS
            # ══════════════════════════════════════════════════════════════════
            st.markdown("#### 🕯️ 1-Hour Forecast — 12 × 5-Minute Candles")
            st.markdown(
                "<p style='color:#888;font-size:13px;margin:-6px 0 10px 0;'>"
                + "✨ <b>Enhanced Candlestick Chart</b> with Technical Overlays "
                + "— SMA-3 · SMA-5 · Bollinger Bands · RSI(5) · 95% Confidence Band</p>",
                unsafe_allow_html=True
            )

            # ── Synthesise OHLC candles from sliding-window closes ────────────
            _n1h = len(closes_1h)
            _seed_ohlc1 = (hash(selected_asset) + int(now_utc.timestamp() // 86400)) % (2 ** 31)
            _rng_ohlc1 = np.random.RandomState(abs(_seed_ohlc1))

            _opens_1h = [closes_1h[0]]
            for _k1 in range(1, _n1h):
                _opens_1h.append(closes_1h[_k1 - 1])

            _shd_sc = max(base_volatility * 0.35, 0.0006)
            _shd_1h = [abs(_rng_ohlc1.normal(_shd_sc, _shd_sc * 0.4)) for _ in range(_n1h)]
            _highs_1h = [max(_opens_1h[_k1], closes_1h[_k1]) * (1.0 + _shd_1h[_k1]) for _k1 in range(_n1h)]
            _lows_1h  = [min(_opens_1h[_k1], closes_1h[_k1]) * (1.0 - _shd_1h[_k1]) for _k1 in range(_n1h)]

            # ── Technical indicators (pure numpy — no talib required) ─────────
            _cl1 = np.array(closes_1h, dtype=float)

            # SMA-3 and SMA-5
            _sma3_1h = np.array([float(np.mean(_cl1[max(0, _i - 2):_i + 1])) for _i in range(_n1h)])
            _sma5_1h = np.array([float(np.mean(_cl1[max(0, _i - 4):_i + 1])) for _i in range(_n1h)])

            # Bollinger Bands (period=5, ±2σ)
            _bb_std_1h = np.array([
                float(np.std(_cl1[max(0, _i - 4):_i + 1])) if _i >= 4 else 0.0
                for _i in range(_n1h)
            ])
            _bb_up_1h = _sma5_1h + 2.0 * _bb_std_1h
            _bb_lo_1h = _sma5_1h - 2.0 * _bb_std_1h

            # RSI (period=5, simple avg-gain / avg-loss method)
            _rsi_1h_vals = np.full(_n1h, np.nan)
            _rsi_p1 = min(5, _n1h - 1)
            if _rsi_p1 >= 2:
                for _ri in range(_rsi_p1, _n1h):
                    _d  = np.diff(_cl1[_ri - _rsi_p1: _ri + 1])
                    _g  = np.where(_d > 0, _d, 0.0).mean()
                    _ls = np.where(_d < 0, -_d, 0.0).mean()
                    _rsi_1h_vals[_ri] = 100.0 if _ls == 0 else 100.0 - 100.0 / (1.0 + _g / max(_ls, 1e-12))

            # ── datetime x-axis (proper time scale for candlestick chart) ─────
            _xt_1h = times_1h

            fig_1h = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.04,
                row_heights=[0.55, 0.23, 0.22],
                subplot_titles=(
                    f"🕯️ {selected_asset} — 1H Candlestick + Technical Overlays (5-Min Intervals)",
                    "📉 RSI (5-Period)  ·  Overbought ≥70  ·  Oversold ≤30",
                    "📊 5-Min Change vs Entry Price %"
                )
            )

            # Row 1: Confidence band (rendered first — behind candles)
            fig_1h.add_trace(go.Scatter(
                x=_xt_1h + _xt_1h[::-1],
                y=conf_up_1h + conf_lo_1h[::-1],
                fill='toself',
                fillcolor='rgba(44,93,131,0.10)',
                line=dict(color='rgba(44,93,131,0.20)', width=1),
                name='95% Conf. Band',
                hoverinfo='skip',
                showlegend=True
            ), row=1, col=1)

            # Row 1: Historical tail (cyan dotted — before NOW)
            if len(asset_df) >= 2 and close_col in asset_df.columns:
                _hist1 = asset_df.tail(min(15, len(asset_df)))
                fig_1h.add_trace(go.Scatter(
                    x=list(_hist1.index),
                    y=_hist1[close_col].values.tolist(),
                    mode='lines',
                    name='Historical',
                    line=dict(color='#00CED1', width=1.8, dash='dot'),
                    hovertemplate='%{customdata}<br>$%{y:,.2f}<extra>Historical</extra>',
                    customdata=[_t.strftime('%H:%M') for _t in _hist1.index]
                ), row=1, col=1)

            # Row 1: Bollinger Bands fill (drawn before candles so candles are on top)
            fig_1h.add_trace(go.Scatter(
                x=_xt_1h, y=_bb_up_1h.tolist(),
                mode='lines', name='BB Upper',
                line=dict(color='rgba(148,103,189,0.65)', width=1, dash='dash'),
                showlegend=True, hoverinfo='skip'
            ), row=1, col=1)
            fig_1h.add_trace(go.Scatter(
                x=_xt_1h, y=_bb_lo_1h.tolist(),
                mode='lines', name='BB Lower',
                line=dict(color='rgba(148,103,189,0.65)', width=1, dash='dash'),
                fill='tonexty', fillcolor='rgba(148,103,189,0.07)',
                showlegend=False, hoverinfo='skip'
            ), row=1, col=1)

            # Row 1: Candlestick (main forecast body)
            fig_1h.add_trace(go.Candlestick(
                x=_xt_1h,
                open=_opens_1h,
                high=_highs_1h,
                low=_lows_1h,
                close=closes_1h,
                name='Forecast Candles',
                increasing_line_color='#26A69A',
                decreasing_line_color='#EF5350',
            ), row=1, col=1)

            # Row 1: SMA overlays
            fig_1h.add_trace(go.Scatter(
                x=_xt_1h, y=_sma3_1h.tolist(),
                mode='lines', name='SMA 3',
                line=dict(color='#FFD700', width=1.5, dash='dot'),
            ), row=1, col=1)
            fig_1h.add_trace(go.Scatter(
                x=_xt_1h, y=_sma5_1h.tolist(),
                mode='lines', name='SMA 5',
                line=dict(color='#FF8C00', width=1.8),
            ), row=1, col=1)

            # Row 1: Live price reference line
            fig_1h.add_hline(
                y=_live_anchor, line_dash='dash', line_color='#FFD700', line_width=1.5,
                annotation_text=f"Live ${_live_anchor:,.2f}",
                annotation_font_color='#FFD700', annotation_position='left',
                row=1, col=1
            )

            # Row 2: RSI panel
            _rsi_plot = [float(v) if not np.isnan(v) else None for v in _rsi_1h_vals]
            fig_1h.add_trace(go.Scatter(
                x=_xt_1h, y=_rsi_plot,
                mode='lines+markers', name='RSI (5)',
                line=dict(color='#A855F7', width=2),
                marker=dict(size=4, color='#A855F7'),
                connectgaps=True,
                hovertemplate='RSI: %{y:.1f}<extra></extra>'
            ), row=2, col=1)
            fig_1h.add_hrect(y0=70, y1=100, fillcolor='rgba(239,83,80,0.07)',  line_width=0, row=2, col=1)
            fig_1h.add_hrect(y0=0,  y1=30,  fillcolor='rgba(38,166,154,0.07)', line_width=0, row=2, col=1)
            fig_1h.add_hline(y=70, line_dash='dash', line_color='rgba(239,83,80,0.55)', line_width=1,
                             annotation_text='OB 70', annotation_font_color='rgba(239,83,80,0.9)',
                             annotation_position='right', row=2, col=1)
            fig_1h.add_hline(y=50, line_dash='dot',  line_color='rgba(150,150,150,0.35)', line_width=1, row=2, col=1)
            fig_1h.add_hline(y=30, line_dash='dash', line_color='rgba(38,166,154,0.55)', line_width=1,
                             annotation_text='OS 30', annotation_font_color='rgba(38,166,154,0.9)',
                             annotation_position='right', row=2, col=1)

            # Row 3: vs-Entry % bars
            changes_1h = [(closes_1h[_k] - a_price) / a_price * 100 for _k in range(len(closes_1h))]
            _bclr_1h = ['#26A69A' if _c >= 0 else '#EF5350' for _c in changes_1h]
            fig_1h.add_trace(go.Bar(
                x=_xt_1h, y=changes_1h,
                name='vs Entry %',
                marker_color=_bclr_1h,
                text=[f"{_c:+.3f}%" for _c in changes_1h],
                textposition='outside',
                hovertemplate='%{customdata}<br>vs Entry: %{y:+.3f}%<extra></extra>',
                customdata=[f"+{int(_t)}min" for _t in _sw1['times']]
            ), row=3, col=1)
            fig_1h.add_hline(y=0, line_color='rgba(0,0,0,0.15)', line_width=1, row=3, col=1)

            fig_1h.update_layout(
                template=None,
                height=690,
                showlegend=True,
                legend=dict(orientation='h', y=1.04, x=0.5, xanchor='center',
                            bgcolor='rgba(255,255,255,0.85)', font=dict(size=10, color='#2c5d83')),
                plot_bgcolor='white',
                paper_bgcolor='white',
                hovermode='x unified',
                xaxis_rangeslider_visible=False,
                margin=dict(l=20, r=20, t=75, b=40),
                title=dict(
                    text=f"🕯️ {selected_asset} — 1-Hour Enhanced Candlestick Forecast (12 × 5-Min Candles)",
                    font=dict(size=16, color='#2c5d83', family='Arial'), x=0.5
                )
            )
            for _row_n in [1, 2, 3]:
                fig_1h.update_xaxes(
                    showgrid=True, gridcolor='rgba(0,0,0,0.09)', gridwidth=0.5,
                    zeroline=False, showline=False,
                    row=_row_n, col=1
                )
            fig_1h.update_yaxes(tickformat='$,.2f', title_text='Price (USD)',
                                  showgrid=True, gridcolor='rgba(0,0,0,0.09)', gridwidth=0.5,
                                  zeroline=False, showline=False, row=1, col=1)
            fig_1h.update_yaxes(title_text='RSI', range=[0, 100],
                                  showgrid=True, gridcolor='rgba(0,0,0,0.09)', gridwidth=0.5,
                                  zeroline=False, row=2, col=1)
            fig_1h.update_yaxes(tickformat='+.3f', title_text='vs Entry %',
                                  showgrid=True, gridcolor='rgba(0,0,0,0.09)', gridwidth=0.5,
                                  zeroline=False, showline=False, row=3, col=1)

            st.plotly_chart(fig_1h, use_container_width=True)
"""

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the exact start and end indices
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'CHART 1' in line and '1-HOUR FORECAST' in line and 'CANDLES' in line:
        start_idx = i - 1  # include the leading border line
    if start_idx is not None and i > start_idx and 'plotly_chart(fig_1h,' in line:
        end_idx = i
        break

if start_idx is None or end_idx is None:
    print(f"ERROR: Could not find section. start={start_idx}, end={end_idx}")
    exit(1)

print(f"Replacing lines {start_idx+1}–{end_idx+1} (1-based)")

# Build new lines list (each line ends with \n already from split)
new_lines = []
for line in NEW_BLOCK.split('\n'):
    new_lines.append(line + '\n')
# The last line should not have a trailing newline (it will be followed by blank line)
if new_lines and new_lines[-1] == '\n':
    new_lines = new_lines[:-1]

result = lines[:start_idx] + new_lines + lines[end_idx + 1:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(result)

print(f"Done. File had {len(lines)} lines, now has {len(result)} lines.")
print(f"Replaced {end_idx - start_idx + 1} old lines with {len(new_lines)} new lines.")
