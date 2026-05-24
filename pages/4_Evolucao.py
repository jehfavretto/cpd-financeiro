"""
Página: Evolução Mensal
Gráficos comparativos dos meses do ano.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import db.client as db
from core.dfc import calcular_dfc, SECOES
from core.parser import MESES_ABREV

st.title("📈 Evolução Mensal")
st.markdown("Comparativo de receitas, custos, despesas e resultado ao longo do ano.")

# ── Seleção de ano ────────────────────────────────────────────────────────────
ano = st.selectbox("Ano", [2026, 2025])
meses_com_dados = db.meses_com_dados(ano)

if not meses_com_dados:
    st.info("Nenhum mês importado ainda. Use **📥 Importar Mês** para começar.")
    st.stop()

# ── Calcula DFC para cada mês ─────────────────────────────────────────────────
@st.cache_data(ttl=120)
def carregar_evolucao(ano: int, meses: tuple) -> pd.DataFrame:
    rows = []
    for mes in meses:
        plano  = db.carregar_plano_contas(mes, ano)
        ajust  = db.carregar_ajustes(mes, ano)
        saldos = db.carregar_saldos(mes, ano)
        if plano.empty:
            continue
        dfc = calcular_dfc(
            plano,
            ar=ajust["AR"],
            ad=ajust["AD"],
            saldo_banco=saldos["saldo_banco"],
        )
        rows.append({
            "mes": mes,
            "mes_nome": MESES_ABREV[mes],
            "receitas":   dfc.total_receitas,
            "custos":     abs(dfc.total_custos),
            "despesas":   abs(dfc.total_despesas),
            "impostos":   abs(dfc.total_impostos),
            "resultado":  dfc.resultado_liquido,
        })
    return pd.DataFrame(rows)

with st.spinner("Carregando dados..."):
    df = carregar_evolucao(ano, tuple(meses_com_dados))

if df.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# ── Gráfico de barras empilhadas — Receitas vs Custos+Despesas ────────────────
st.subheader("Receitas × Custos + Despesas + Impostos")

fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    name="Receitas", x=df["mes_nome"], y=df["receitas"],
    marker_color="#2A9D8F", text=df["receitas"].apply(lambda v: f"R${v/1000:.0f}k"),
    textposition="auto",
))
fig_bar.add_trace(go.Bar(
    name="Custos", x=df["mes_nome"], y=df["custos"],
    marker_color="#E76F51",
))
fig_bar.add_trace(go.Bar(
    name="Despesas", x=df["mes_nome"], y=df["despesas"],
    marker_color="#E9C46A",
))
fig_bar.add_trace(go.Bar(
    name="Impostos", x=df["mes_nome"], y=df["impostos"],
    marker_color="#264653",
))
fig_bar.update_layout(
    barmode="group", height=380,
    yaxis=dict(tickprefix="R$ ", tickformat=",.0f"),
    plot_bgcolor="white", legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── Resultado Líquido por mês ─────────────────────────────────────────────────
st.subheader("Resultado Líquido por mês")

colors = ["#2A9D8F" if v >= 0 else "#E63946" for v in df["resultado"]]
fig_res = go.Figure(go.Bar(
    x=df["mes_nome"],
    y=df["resultado"],
    marker_color=colors,
    text=df["resultado"].apply(lambda v: f"R$ {v:,.0f}"),
    textposition="outside",
))
fig_res.add_hline(y=0, line_dash="dash", line_color="gray")
fig_res.update_layout(
    height=350,
    yaxis=dict(tickprefix="R$ ", tickformat=",.0f"),
    plot_bgcolor="white",
    margin=dict(t=10, b=10),
    showlegend=False,
)
st.plotly_chart(fig_res, use_container_width=True)

st.divider()

# ── Tabela resumo ─────────────────────────────────────────────────────────────
st.subheader("Tabela resumo")

df_tabela = df[[
    "mes_nome", "receitas", "custos", "despesas", "impostos", "resultado"
]].copy()
df_tabela.columns = ["Mês", "Receitas", "Custos", "Despesas", "Impostos", "Resultado"]

for col in ["Receitas", "Custos", "Despesas", "Impostos", "Resultado"]:
    df_tabela[col] = df_tabela[col].apply(lambda v: f"R$ {v:,.2f}")

# Totais
totais = df[["receitas", "custos", "despesas", "impostos", "resultado"]].sum()
total_row = pd.DataFrame([{
    "Mês": "**TOTAL**",
    "Receitas": f"R$ {totais['receitas']:,.2f}",
    "Custos":   f"R$ {totais['custos']:,.2f}",
    "Despesas": f"R$ {totais['despesas']:,.2f}",
    "Impostos": f"R$ {totais['impostos']:,.2f}",
    "Resultado":f"R$ {totais['resultado']:,.2f}",
}])

df_tabela = pd.concat([df_tabela, total_row], ignore_index=True)
st.dataframe(df_tabela, use_container_width=True, hide_index=True)
