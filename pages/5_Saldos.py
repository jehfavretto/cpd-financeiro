"""
Página: Saldos
Saldo bancário, aplicação e caixa por mês.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import db.client as db
from core.parser import MESES_ABREV

st.title("💰 Saldos")
st.markdown("Saldo em banco, aplicação e caixa ao longo do ano.")

# ── Seleção de ano ────────────────────────────────────────────────────────────
ano = st.selectbox("Ano", [2026, 2025])
meses_com_dados = db.meses_com_dados(ano)

if not meses_com_dados:
    st.info("Nenhum mês importado ainda. Use **📥 Importar Mês** para começar.")
    st.stop()

# ── Carrega saldos do ano ─────────────────────────────────────────────────────
saldos_df = db.carregar_saldos_ano(ano)

if saldos_df.empty:
    st.warning("Nenhum saldo registrado para este ano.")
    st.stop()

saldos_df["mes_nome"] = saldos_df["mes"].map(MESES_ABREV)
saldos_df["total"] = (
    saldos_df["saldo_banco"]
    + saldos_df["saldo_aplicacao"]
    + saldos_df["saldo_caixa"]
)

# ── KPIs do último mês ────────────────────────────────────────────────────────
ultimo = saldos_df.iloc[-1]
st.subheader(f"Posição em {MESES_ABREV[int(ultimo['mes'])]}/{ano}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("🏦 Banco",       f"R$ {ultimo['saldo_banco']:,.2f}")
c2.metric("📈 Aplicação",   f"R$ {ultimo['saldo_aplicacao']:,.2f}")
c3.metric("💵 Caixa",       f"R$ {ultimo['saldo_caixa']:,.2f}")
c4.metric("✅ Total",        f"R$ {ultimo['total']:,.2f}")

st.divider()

# ── Editar saldos de um mês ────────────────────────────────────────────────────
with st.expander("✏️ Editar saldos de um mês", expanded=False):
    mes_edit = st.selectbox(
        "Mês para editar", meses_com_dados,
        format_func=lambda m: f"{MESES_ABREV[m]}/{ano}",
        key="mes_edit",
    )
    saldo_atual = db.carregar_saldos(mes_edit, ano)

    c1, c2, c3 = st.columns(3)
    with c1:
        novo_banco = st.number_input(
            "Banco (R$)", value=float(saldo_atual["saldo_banco"]),
            format="%.2f", step=100.0, key="edit_banco"
        )
    with c2:
        novo_aplic = st.number_input(
            "Aplicação (R$)", value=float(saldo_atual["saldo_aplicacao"]),
            format="%.2f", step=100.0, key="edit_aplic"
        )
    with c3:
        novo_caixa = st.number_input(
            "Caixa — dinheiro físico (R$)", value=float(saldo_atual["saldo_caixa"]),
            format="%.2f", step=10.0, key="edit_caixa"
        )

    if st.button("Salvar saldos", type="secondary"):
        db.salvar_saldos(mes_edit, ano, novo_banco, novo_aplic, novo_caixa)
        st.success("Saldos atualizados!")
        st.rerun()

st.divider()

# ── Gráfico de área empilhada ─────────────────────────────────────────────────
st.subheader("Evolução dos saldos")

fig = go.Figure()
fig.add_trace(go.Scatter(
    name="Banco", x=saldos_df["mes_nome"], y=saldos_df["saldo_banco"],
    fill="tozeroy", mode="lines+markers",
    line=dict(color="#1E6FBA", width=2),
    marker=dict(size=6),
))
fig.add_trace(go.Scatter(
    name="Aplicação", x=saldos_df["mes_nome"], y=saldos_df["saldo_aplicacao"],
    fill="tozeroy", mode="lines+markers",
    line=dict(color="#2A9D8F", width=2),
    marker=dict(size=6),
))
fig.add_trace(go.Scatter(
    name="Caixa", x=saldos_df["mes_nome"], y=saldos_df["saldo_caixa"],
    fill="tozeroy", mode="lines+markers",
    line=dict(color="#E9C46A", width=2),
    marker=dict(size=6),
))
fig.update_layout(
    height=380,
    yaxis=dict(tickprefix="R$ ", tickformat=",.0f"),
    plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Tabela ────────────────────────────────────────────────────────────────────
st.subheader("Tabela de saldos")

df_tab = saldos_df[["mes_nome", "saldo_banco", "saldo_aplicacao",
                     "saldo_caixa", "total"]].copy()
df_tab.columns = ["Mês", "Banco", "Aplicação", "Caixa", "Total"]
for col in ["Banco", "Aplicação", "Caixa", "Total"]:
    df_tab[col] = df_tab[col].apply(lambda v: f"R$ {v:,.2f}")

st.dataframe(df_tab, use_container_width=True, hide_index=True)
