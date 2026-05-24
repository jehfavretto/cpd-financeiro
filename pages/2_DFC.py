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

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📈 Receitas",    f"R$ {dfc.total_receitas:,.2f}",
          delta_color="normal")
c2.metric("🏭 Custos",      f"R$ {dfc.total_custos:,.2f}",
          delta=f"R$ {dfc.total_custos:,.2f}", delta_color="inverse")
c3.metric("🏢 Despesas",    f"R$ {dfc.total_despesas:,.2f}",
          delta=f"R$ {dfc.total_despesas:,.2f}", delta_color="inverse")
c4.metric("🏛️ Impostos",   f"R$ {dfc.total_impostos:,.2f}",
          delta=f"R$ {dfc.total_impostos:,.2f}", delta_color="inverse")

resultado = dfc.resultado_liquido
c5.metric(
    "💡 Resultado Líquido", f"R$ {resultado:,.2f}",
    delta=f"R$ {resultado:,.2f}",
    delta_color="normal" if resultado >= 0 else "inverse",
)

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

# ── Tabela DFC detalhada ──────────────────────────────────────────────────────
st.subheader("Demonstração completa")

# Monta tabela de exibição
_desc_por_codigo = dict(zip(plano_df["codigo"], plano_df["descricao"]))

rows_display = []
for sec_prefix, sec_info in SECOES.items():
    sec_total = dfc.total_secao(sec_prefix)
    if sec_prefix == "1.":
        sec_total += dfc.ar
    if sec_prefix == "3.":
        sec_total += dfc.ad

    rows_display.append({
        "Código": sec_prefix,
        "Descrição": f"**{sec_info['label']}**",
        "Valor (R$)": sec_total,
        "_nivel": "secao",
    })

    grupos_da_secao = {k: v for k, v in GRUPOS.items() if k.startswith(sec_prefix[0])}
    for grp_prefix, grp_label in grupos_da_secao.items():
        contas = dfc.dados.get(sec_prefix, {}).get(grp_prefix, {})
        grp_total = sum(contas.values())

        rows_display.append({
            "Código": grp_prefix,
            "Descrição": f"  {grp_label}",
            "Valor (R$)": grp_total,
            "_nivel": "grupo",
        })

        for cod, val in sorted(contas.items()):
            if val == 0:
                continue
            rows_display.append({
                "Código": cod,
                "Descrição": f"    {_desc_por_codigo.get(cod, cod)}",
                "Valor (R$)": val,
                "_nivel": "conta",
            })

    if sec_prefix == "1." and dfc.ar != 0:
        rows_display.append({"Código": "AR", "Descrição": "  AJUSTE RECEITA",
                              "Valor (R$)": dfc.ar, "_nivel": "ajuste"})
    if sec_prefix == "3." and dfc.ad != 0:
        rows_display.append({"Código": "AD", "Descrição": "  AJUSTE DESPESA",
                              "Valor (R$)": dfc.ad, "_nivel": "ajuste"})

# Resultado final
rows_display.append({"Código": "", "Descrição": "**RESULTADO LÍQUIDO**",
                     "Valor (R$)": dfc.resultado_liquido, "_nivel": "resultado"})

df_display = pd.DataFrame(rows_display)

# Formata valores
def fmt_valor(v, nivel):
    if v == 0 and nivel == "conta":
        return ""
    cor = "color: green" if v > 0 else ("color: red" if v < 0 else "color: gray")
    return f"R$ {v:,.2f}"

# Exibe com st.dataframe + highlight por nível
st.dataframe(
    df_display[["Código", "Descrição", "Valor (R$)"]].assign(
        **{"Valor (R$)": df_display.apply(
            lambda r: f"R$ {r['Valor (R$)']:,.2f}" if r["Valor (R$)"] != 0 else "—", axis=1
        )}
    ),
    use_container_width=True,
    height=700,
    hide_index=True,
)

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
