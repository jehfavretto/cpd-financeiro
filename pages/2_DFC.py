"""
Página: DFC / Resumo
Demonstração de Fluxo de Caixa — replica a aba Resumo do Book.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.dfc import calcular_dfc, SECOES, GRUPOS
import db.client as db
from core.parser import MESES_ABREV

st.title("📊 DFC — Demonstração de Fluxo de Caixa")

# ── Seleção de mês ────────────────────────────────────────────────────────────
anos_disponiveis = [2026, 2025]  # expandir conforme necessário
col1, col2 = st.columns([1, 3])
with col1:
    ano = st.selectbox("Ano", anos_disponiveis, index=0)

meses_com_dados = db.meses_com_dados(ano)
if not meses_com_dados:
    st.info("Nenhum mês importado ainda. Use **📥 Importar Mês** para começar.")
    st.stop()

with col2:
    mes_opcoes = {m: f"{MESES_ABREV[m]}/{ano}" for m in meses_com_dados}
    mes = st.selectbox("Mês", list(mes_opcoes.keys()),
                       format_func=lambda m: mes_opcoes[m],
                       index=len(meses_com_dados) - 1)

# ── Carrega dados ─────────────────────────────────────────────────────────────
plano_df  = db.carregar_plano_contas(mes, ano)
ajustes   = db.carregar_ajustes(mes, ano)
saldos    = db.carregar_saldos(mes, ano)

if plano_df.empty:
    st.warning("PlanoDeContas não encontrado para este mês.")
    st.stop()

dfc = calcular_dfc(
    plano_df,
    ar=ajustes["AR"],
    ad=ajustes["AD"],
    saldo_anterior=saldos.get("saldo_anterior", 0.0),
    saldo_banco=saldos["saldo_banco"],
    saldo_aplicacao=saldos["saldo_aplicacao"],
    saldo_caixa=saldos["saldo_caixa"],
)

# ── KPIs principais ───────────────────────────────────────────────────────────
st.subheader(f"{MESES_ABREV[mes]}/{ano}")

def _br(v: float) -> str:
    """Formata valor em Real brasileiro sem centavos para KPI."""
    return f"R$ {abs(v):,.0f}".replace(",", ".")

resultado = dfc.resultado_liquido
res_color  = "#1a7f37" if resultado >= 0 else "#C4153A"
res_bg     = "#eaffea" if resultado >= 0 else "#fff0f0"
res_sinal  = "▲" if resultado >= 0 else "▼"

st.markdown(f"""
<div style="display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap;">
  <div style="flex:1; min-width:140px; background:#f8f9fb; border-left:4px solid #1C2B5F;
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:#555; margin-bottom:4px;">📈 Receitas</div>
    <div style="font-size:1.35rem; font-weight:700; color:#1C2B5F;">{_br(dfc.total_receitas)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:#f8f9fb; border-left:4px solid #C4153A;
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:#555; margin-bottom:4px;">🏭 Custos</div>
    <div style="font-size:1.35rem; font-weight:700; color:#C4153A;">{_br(dfc.total_custos)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:#f8f9fb; border-left:4px solid #C4153A;
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:#555; margin-bottom:4px;">🏢 Despesas</div>
    <div style="font-size:1.35rem; font-weight:700; color:#C4153A;">{_br(dfc.total_despesas)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:#f8f9fb; border-left:4px solid #C4153A;
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:#555; margin-bottom:4px;">🏛️ Impostos</div>
    <div style="font-size:1.35rem; font-weight:700; color:#C4153A;">{_br(dfc.total_impostos)}</div>
  </div>
  <div style="flex:1.2; min-width:160px; background:{res_bg}; border-left:4px solid {res_color};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:#555; margin-bottom:4px;">💡 Resultado Líquido</div>
    <div style="font-size:1.35rem; font-weight:700; color:{res_color};">{res_sinal} {_br(resultado)}</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Ajustes manuais (AR / AD) ─────────────────────────────────────────────────
with st.expander("✏️ Ajustes manuais (AR / AD)", expanded=False):
    st.markdown(
        "Preenchidos manualmente, como no Book Excel. "
        "**AR** reduz Receitas, **AD** reduz Despesas."
    )
    c1, c2 = st.columns(2)
    with c1:
        novo_ar = st.number_input("AR — Ajuste Receita (R$)",
                                  value=float(ajustes["AR"]), format="%.2f", step=100.0)
    with c2:
        novo_ad = st.number_input("AD — Ajuste Despesa (R$)",
                                  value=float(ajustes["AD"]), format="%.2f", step=100.0)
    if st.button("Salvar ajustes", type="secondary"):
        db.salvar_ajuste(mes, ano, "AR", novo_ar)
        db.salvar_ajuste(mes, ano, "AD", novo_ad)
        st.success("Ajustes salvos!")
        st.rerun()

st.divider()

# ── Demonstração: resumo compacto + analítico retrátil ────────────────────────
st.subheader("Demonstração")

_desc_por_codigo = dict(zip(plano_df["codigo"], plano_df["descricao"]))

# Calcula totais por seção
sec_totals = {}
for sp, si in SECOES.items():
    t = dfc.total_secao(sp)
    if sp == "1.":
        t += dfc.ar
    if sp == "3.":
        t += dfc.ad
    sec_totals[sp] = t

# Tabela resumo compacta (sempre visível)
resumo = [
    {"Seção": si["label"], "Valor (R$)": f"R$ {sec_totals[sp]:,.2f}"}
    for sp, si in SECOES.items()
]
resumo.append({"Seção": "RESULTADO LÍQUIDO", "Valor (R$)": f"R$ {dfc.resultado_liquido:,.2f}"})
st.dataframe(pd.DataFrame(resumo), hide_index=True, use_container_width=True, height=215)

# Expanders analíticos por seção
for sp, si in SECOES.items():
    with st.expander(f"{si['label']}  —  R$ {sec_totals[sp]:,.2f}"):
        det = []
        for grp_prefix, grp_label in {k: v for k, v in GRUPOS.items() if k.startswith(sp[0])}.items():
            contas = dfc.dados.get(sp, {}).get(grp_prefix, {})
            grp_total = sum(contas.values())
            if not contas:
                continue
            det.append({"Descrição": grp_label,
                        "Valor (R$)": f"R$ {grp_total:,.2f}"})
            for cod, val in sorted(contas.items()):
                if val == 0:
                    continue
                det.append({"Descrição": f"    {_desc_por_codigo.get(cod, cod)}",
                            "Valor (R$)": f"R$ {val:,.2f}"})
        if sp == "1." and dfc.ar != 0:
            det.append({"Descrição": "    Ajuste Receita (AR)",
                        "Valor (R$)": f"R$ {dfc.ar:,.2f}"})
        if sp == "3." and dfc.ad != 0:
            det.append({"Descrição": "    Ajuste Despesa (AD)",
                        "Valor (R$)": f"R$ {dfc.ad:,.2f}"})
        if det:
            st.dataframe(pd.DataFrame(det), hide_index=True, use_container_width=True)
        else:
            st.caption("Sem lançamentos nesta seção.")

st.divider()

# ── Gráfico Waterfall ─────────────────────────────────────────────────────────
st.subheader("📊 Resultado do mês")

fig = go.Figure(go.Waterfall(
    name="DFC",
    orientation="v",
    measure=["absolute", "relative", "relative", "relative", "total"],
    x=["Receitas", "Custos", "Despesas", "Impostos", "Resultado"],
    y=[
        dfc.total_receitas,
        dfc.total_custos,
        dfc.total_despesas,
        dfc.total_impostos,
        dfc.resultado_liquido,
    ],
    connector={"line": {"color": "rgb(63, 63, 63)"}},
    decreasing={"marker": {"color": "#E63946"}},
    increasing={"marker": {"color": "#2A9D8F"}},
    totals={"marker": {"color": "#1E6FBA" if dfc.resultado_liquido >= 0 else "#E63946"}},
    texttemplate="R$ %{y:,.0f}",
    textposition="outside",
))

fig.update_layout(
    height=420,
    margin=dict(t=30, b=10, l=10, r=10),
    plot_bgcolor="white",
    yaxis=dict(tickprefix="R$ ", tickformat=",.0f"),
    showlegend=False,
)

st.plotly_chart(fig, use_container_width=True)
