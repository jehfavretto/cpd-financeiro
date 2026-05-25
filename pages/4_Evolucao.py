"""
Página: Evolução Mensal
Comparativos mês a mês e acumulado do ano.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import db.client as db
from core.dfc import calcular_dfc, SECOES
from core.parser import MESES_ABREV
from core.utils import fmt_br, fmt_br_kpi

st.title("📈 Evolução Mensal")

# ── Seleção de ano ────────────────────────────────────────────────────────────
ano = st.selectbox("Ano", [2026, 2025])
meses_com_dados = db.meses_com_dados(ano)

if not meses_com_dados:
    st.info("Nenhum mês importado ainda. Use **📥 Importar Mês** para começar.")
    st.stop()

# ── Carrega e calcula DFC de cada mês ─────────────────────────────────────────
@st.cache_data(ttl=120)
def carregar_evolucao(ano: int, meses: tuple) -> pd.DataFrame:
    rows = []
    for mes in meses:
        plano  = db.carregar_plano_contas(mes, ano)
        ajust  = db.carregar_ajustes(mes, ano)
        saldos = db.carregar_saldos(mes, ano)
        if plano.empty:
            continue
        dfc = calcular_dfc(plano, ar=ajust["AR"], ad=ajust["AD"],
                           saldo_banco=saldos["saldo_banco"])
        rows.append({
            "mes":       mes,
            "label":     MESES_ABREV[mes],
            "receitas":  dfc.total_receitas,
            "custos":    abs(dfc.total_custos),
            "despesas":  abs(dfc.total_despesas),
            "impostos":  abs(dfc.total_impostos),
            "saidas":    abs(dfc.total_custos) + abs(dfc.total_despesas) + abs(dfc.total_impostos),
            "resultado": dfc.resultado_liquido,
        })
    return pd.DataFrame(rows)

with st.spinner("Carregando dados..."):
    df = carregar_evolucao(ano, tuple(meses_com_dados))

if df.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

n = len(df)

# ── KPIs acumulados do ano ────────────────────────────────────────────────────
_br = fmt_br_kpi

res_ytd    = df["resultado"].sum()
res_color  = "#1a7f37" if res_ytd >= 0 else "#C4153A"
res_bg     = "#eaffea" if res_ytd >= 0 else "#fff0f0"
res_sinal  = "▲" if res_ytd >= 0 else "▼"
media_res  = res_ytd / n

st.markdown(f"""
<div style="display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap;">
  <div style="flex:1; min-width:130px; background:#f8f9fb; border-left:4px solid #1C2B5F;
              border-radius:6px; padding:12px 14px;">
    <div style="font-size:0.75rem; color:#666; margin-bottom:3px;">📅 Meses importados</div>
    <div style="font-size:1.3rem; font-weight:700; color:#1C2B5F;">{n}</div>
  </div>
  <div style="flex:1.4; min-width:150px; background:#f8f9fb; border-left:4px solid #1C2B5F;
              border-radius:6px; padding:12px 14px;">
    <div style="font-size:0.75rem; color:#666; margin-bottom:3px;">📈 Receitas acumuladas</div>
    <div style="font-size:1.3rem; font-weight:700; color:#1C2B5F;">{_br(df['receitas'].sum())}</div>
  </div>
  <div style="flex:1.4; min-width:150px; background:#f8f9fb; border-left:4px solid #C4153A;
              border-radius:6px; padding:12px 14px;">
    <div style="font-size:0.75rem; color:#666; margin-bottom:3px;">📉 Saídas acumuladas</div>
    <div style="font-size:1.3rem; font-weight:700; color:#C4153A;">{_br(df['saidas'].sum())}</div>
  </div>
  <div style="flex:1.4; min-width:150px; background:{res_bg}; border-left:4px solid {res_color};
              border-radius:6px; padding:12px 14px;">
    <div style="font-size:0.75rem; color:#666; margin-bottom:3px;">💡 Resultado acumulado</div>
    <div style="font-size:1.3rem; font-weight:700; color:{res_color};">{res_sinal} {_br(res_ytd)}</div>
  </div>
  <div style="flex:1.4; min-width:150px; background:{res_bg}; border-left:4px solid {res_color};
              border-radius:6px; padding:12px 14px;">
    <div style="font-size:0.75rem; color:#666; margin-bottom:3px;">📊 Média mensal</div>
    <div style="font-size:1.3rem; font-weight:700; color:{res_color};">{res_sinal} {_br(media_res)}</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Gráfico: Receitas × Saídas por mês ───────────────────────────────────────
st.subheader("Receitas × Saídas por mês")

fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    name="Receitas", x=df["label"], y=df["receitas"],
    marker_color="#1C2B5F",
    text=df["receitas"].apply(lambda v: f"R${v/1000:.0f}k"),
    textposition="auto", textfont=dict(color="white", size=11),
))
fig_bar.add_trace(go.Bar(
    name="Saídas totais", x=df["label"], y=df["saidas"],
    marker_color="#C4153A",
    text=df["saidas"].apply(lambda v: f"R${v/1000:.0f}k"),
    textposition="auto", textfont=dict(color="white", size=11),
))
fig_bar.update_layout(
    barmode="group", height=360,
    yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="#eee"),
    plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── Gráfico: Resultado Líquido por mês ───────────────────────────────────────
st.subheader("Resultado Líquido por mês")

colors = ["#1a7f37" if v >= 0 else "#C4153A" for v in df["resultado"]]
fig_res = go.Figure()
fig_res.add_trace(go.Bar(
    x=df["label"], y=df["resultado"],
    marker_color=colors,
    text=df["resultado"].apply(lambda v: f"R$ {v:,.0f}".replace(",", ".")),
    textposition="outside",
))
# Linha de tendência (média móvel simples)
if n >= 2:
    fig_res.add_trace(go.Scatter(
        x=df["label"], y=df["resultado"].expanding().mean(),
        mode="lines+markers", name="Média acumulada",
        line=dict(color="#1C2B5F", dash="dot", width=2),
        marker=dict(size=6),
    ))
fig_res.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
fig_res.update_layout(
    height=340,
    yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="#eee"),
    plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_res, use_container_width=True)

st.divider()

# ── Tabela resumo ─────────────────────────────────────────────────────────────
st.subheader("Tabela resumo")

_fmt = fmt_br

tab = df[["label", "receitas", "saidas", "resultado"]].copy()
tab.columns = ["Mês", "Receitas", "Saídas", "Resultado"]
for col in ["Receitas", "Saídas", "Resultado"]:
    tab[col] = tab[col].apply(_fmt)

# Linha de total
tot_rec = df["receitas"].sum()
tot_sai = df["saidas"].sum()
tot_res = df["resultado"].sum()
total_row = pd.DataFrame([{
    "Mês":       "TOTAL",
    "Receitas":  _fmt(tot_rec),
    "Saídas":    _fmt(tot_sai),
    "Resultado": _fmt(tot_res),
}])

st.dataframe(
    pd.concat([tab, total_row], ignore_index=True),
    use_container_width=True,
    hide_index=True,
)

# Detalhamento por componente (retrátil)
with st.expander("📋 Ver detalhamento (Custos / Despesas / Impostos)"):
    det = df[["label", "receitas", "custos", "despesas", "impostos", "resultado"]].copy()
    det.columns = ["Mês", "Receitas", "Custos", "Despesas", "Impostos", "Resultado"]
    for col in ["Receitas", "Custos", "Despesas", "Impostos", "Resultado"]:
        det[col] = det[col].apply(_fmt)
    tot_row2 = pd.DataFrame([{
        "Mês": "TOTAL",
        "Receitas":  _fmt(df["receitas"].sum()),
        "Custos":    _fmt(df["custos"].sum()),
        "Despesas":  _fmt(df["despesas"].sum()),
        "Impostos":  _fmt(df["impostos"].sum()),
        "Resultado": _fmt(df["resultado"].sum()),
    }])
    st.dataframe(
        pd.concat([det, tot_row2], ignore_index=True),
        use_container_width=True,
        hide_index=True,
    )
