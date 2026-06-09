"""
Página: Saldos
Saldo bancário, aplicação e caixa por mês.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import db.client as db
from core.parser import MESES_ABREV
from core.utils import fmt_br

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
ultimo   = saldos_df.iloc[-1]
banco    = float(ultimo["saldo_banco"])
aplicacao= float(ultimo["saldo_aplicacao"])
caixa    = float(ultimo["saldo_caixa"])
total    = float(ultimo["total"])

# Cores dinâmicas conforme o tema
_dark  = st.session_state.get("tema", "light") == "dark"
_card  = "#1A2550" if _dark else "#f8f9fb"
_txt   = "#E8EDF6" if _dark else "#1C2B5F"
_txt2  = "#8FA0C0" if _dark else "#555"

tot_color = ("#2ed64f" if _dark else "#1a7f37") if total >= 0 else ("#E63A5C" if _dark else "#C4153A")
tot_bg    = ("#0d2a1a" if _dark else "#eaffea") if total >= 0 else ("#2a0d14" if _dark else "#fff0f0")

st.subheader(f"Posição em {MESES_ABREV[int(ultimo['mes'])]}/{ano}")
st.markdown(f"""
<div style="display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap;">
  <div style="flex:1; min-width:150px; background:{_card}; border-left:4px solid {_txt};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">🏦 Banco</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_txt};">{fmt_br(banco)}</div>
  </div>
  <div style="flex:1; min-width:150px; background:{_card}; border-left:4px solid #2A9D8F;
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">📈 Aplicação</div>
    <div style="font-size:1.35rem; font-weight:700; color:#2A9D8F;">{fmt_br(aplicacao)}</div>
  </div>
  <div style="flex:1; min-width:150px; background:{_card}; border-left:4px solid #E9A020;
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">💵 Caixa</div>
    <div style="font-size:1.35rem; font-weight:700; color:#E9A020;">{fmt_br(caixa)}</div>
  </div>
  <div style="flex:1; min-width:150px; background:{tot_bg}; border-left:4px solid {tot_color};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">✅ Total</div>
    <div style="font-size:1.35rem; font-weight:700; color:{tot_color};">{fmt_br(total)}</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Editar saldos de um mês ────────────────────────────────────────────────────
with st.expander("✏️ Editar saldos de um mês", expanded=st.session_state.get("edit_saldos_open", False)):
    mes_edit = st.selectbox(
        "Mês para editar", meses_com_dados,
        format_func=lambda m: f"{MESES_ABREV[m]}/{ano}",
        key="mes_edit",
    )
    saldo_atual = db.carregar_saldos(mes_edit, ano)

    c1, c2, c3 = st.columns(3)
    with c1:
        novo_banco = st.number_input(
            "🏦 Saldo Banco (R$)", value=float(saldo_atual["saldo_banco"]),
            format="%.2f", step=100.0, key="edit_banco"
        )
    with c2:
        novo_aplic = st.number_input(
            "📈 Saldo Aplicação (R$)", value=float(saldo_atual["saldo_aplicacao"]),
            format="%.2f", step=100.0, key="edit_aplic"
        )
    with c3:
        novo_caixa = st.number_input(
            "💵 Saldo Caixa (R$)", value=float(saldo_atual["saldo_caixa"]),
            format="%.2f", step=10.0, key="edit_caixa"
        )

    st.caption("Rendimentos e resgates do fundo de investimento — conforme Extrato de Fundos")
    c4, c5 = st.columns(2)
    with c4:
        novo_rendimento = st.number_input(
            "💹 Rendimento da Aplicação no mês (R$)",
            value=float(saldo_atual.get("rendimento_aplicacao") or 0.0),
            format="%.2f", step=10.0, key="edit_rendimento",
            help="Rendimento Bruto no Mês — conforme Extrato de Fundos CEF"
        )
    with c5:
        novo_resgate = st.number_input(
            "↩️ Resgate da Aplicação no mês (R$)",
            value=float(saldo_atual.get("resgate_aplicacao") or 0.0),
            format="%.2f", step=100.0, key="edit_resgate",
            help="Resgates realizados no mês — conforme Extrato de Fundos CEF"
        )

    if st.button("Salvar saldos", type="primary"):
        db.salvar_saldos(
            mes_edit, ano,
            novo_banco, novo_aplic, novo_caixa,
            rendimento_aplicacao=novo_rendimento,
            resgate_aplicacao=novo_resgate,
        )
        st.session_state["edit_saldos_open"] = False
        st.toast("✅ Saldos atualizados!", icon="✅")
        st.rerun()

st.divider()

# ── Gráfico de linha — evolução dos saldos ────────────────────────────────────
st.subheader("Evolução dos saldos")

_plot_bg   = "#0F1B35" if _dark else "white"
_grid_clr  = "#1E3060" if _dark else "#eee"
_axis_clr  = "#8FA0C0" if _dark else "#444"
# Cores das séries — versões mais claras no escuro para ficarem visíveis
_c_banco   = "#5B8BDF" if _dark else "#1C2B5F"
_c_aplic   = "#3DC5B7" if _dark else "#2A9D8F"

fig = go.Figure()
fig.add_trace(go.Scatter(
    name="Banco", x=saldos_df["mes_nome"], y=saldos_df["saldo_banco"],
    mode="lines+markers",
    line=dict(color=_c_banco, width=2),
    marker=dict(size=7),
))
fig.add_trace(go.Scatter(
    name="Aplicação", x=saldos_df["mes_nome"], y=saldos_df["saldo_aplicacao"],
    mode="lines+markers",
    line=dict(color=_c_aplic, width=2),
    marker=dict(size=7),
))
fig.add_trace(go.Scatter(
    name="Caixa", x=saldos_df["mes_nome"], y=saldos_df["saldo_caixa"],
    mode="lines+markers",
    line=dict(color="#E9A020", width=2),
    marker=dict(size=7),
))
fig.add_trace(go.Scatter(
    name="Total", x=saldos_df["mes_nome"], y=saldos_df["total"],
    mode="lines+markers",
    line=dict(color="#C4153A", width=2, dash="dot"),
    marker=dict(size=7),
))

fig.update_layout(
    height=380,
    yaxis=dict(tickformat=",.0f", gridcolor=_grid_clr, color=_axis_clr),
    xaxis=dict(color=_axis_clr),
    plot_bgcolor=_plot_bg,
    paper_bgcolor=_plot_bg,
    font=dict(color=_axis_clr),
    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                font=dict(color=_axis_clr)),
    margin=dict(t=10, b=10),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Tabela ────────────────────────────────────────────────────────────────────
st.subheader("Tabela de saldos")

df_tab = saldos_df[["mes_nome", "saldo_banco", "saldo_aplicacao",
                     "saldo_caixa", "total"]].copy()
df_tab.columns = ["Mês", "Banco", "Aplicação", "Caixa", "Total"]
for col in ["Banco", "Aplicação", "Caixa", "Total"]:
    df_tab[col] = df_tab[col].apply(fmt_br)

st.dataframe(df_tab, use_container_width=True, hide_index=True)
