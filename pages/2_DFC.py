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
from core.utils import fmt_br, fmt_br_kpi
from core.exportar import gerar_excel, gerar_pdf_ceo

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

_rendimento_aplic = float(saldos.get("rendimento_aplicacao", 0.0))
_resgate_aplic    = float(saldos.get("resgate_aplicacao", 0.0))

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

_br = fmt_br_kpi  # alias para KPI cards (sem centavos)

# ── Cores dinâmicas conforme o tema ──────────────────────────────────────────
_dark     = st.session_state.get("tema", "light") == "dark"
_card     = "#1A2550"  if _dark else "#f8f9fb"
_txt      = "#E8EDF6"  if _dark else "#1C2B5F"
_txt2     = "#8FA0C0"  if _dark else "#555555"
_accent   = "#E63A5C"  if _dark else "#C4153A"

resultado = dfc.resultado_liquido
res_color  = ("#2ed64f"  if _dark else "#1a7f37") if resultado >= 0 else _accent
res_bg     = ("#0d2a1a"  if _dark else "#eaffea") if resultado >= 0 else ("#2a0d14" if _dark else "#fff0f0")
res_sinal  = "▲" if resultado >= 0 else "▼"

st.markdown(f"""
<div style="display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap;">
  <div style="flex:1; min-width:140px; background:{_card}; border-left:4px solid {_txt};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">📈 Receitas</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_txt};">{_br(dfc.total_receitas)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:{_card}; border-left:4px solid {_accent};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">🏭 Custos</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_accent};">{_br(dfc.total_custos)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:{_card}; border-left:4px solid {_accent};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">🏢 Despesas</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_accent};">{_br(dfc.total_despesas)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:{_card}; border-left:4px solid {_accent};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">🏛️ Impostos</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_accent};">{_br(dfc.total_impostos)}</div>
  </div>
  <div style="flex:1.2; min-width:160px; background:{res_bg}; border-left:4px solid {res_color};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">💡 Resultado Líquido</div>
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

_fmt_br = fmt_br  # alias para tabelas (com centavos)

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
    {"Seção": si["label"], "Valor (R$)": _fmt_br(sec_totals[sp])}
    for sp, si in SECOES.items()
]
if _rendimento_aplic:
    resumo.append({"Seção": "💹 Rendimento da Aplicação", "Valor (R$)": _fmt_br(_rendimento_aplic)})
if _resgate_aplic:
    resumo.append({"Seção": "↩️ Resgate da Aplicação", "Valor (R$)": _fmt_br(_resgate_aplic)})
_resultado_total = dfc.resultado_liquido + _rendimento_aplic + _resgate_aplic
resumo.append({"Seção": "RESULTADO LÍQUIDO", "Valor (R$)": _fmt_br(_resultado_total)})
_altura_resumo = 215 + (26 * ((_rendimento_aplic != 0) + (_resgate_aplic != 0)))
st.dataframe(pd.DataFrame(resumo), hide_index=True, use_container_width=True, height=_altura_resumo)

# Expanders analíticos por seção
for sp, si in SECOES.items():
    with st.expander(f"{si['label']}  —  {_fmt_br(sec_totals[sp])}"):
        det = []
        for grp_prefix, grp_label in {k: v for k, v in GRUPOS.items() if k.startswith(sp[0])}.items():
            contas = dfc.dados.get(sp, {}).get(grp_prefix, {})
            grp_total = sum(contas.values())
            if not contas:
                continue
            det.append({"Descrição": grp_label,
                        "Valor (R$)": _fmt_br(grp_total)})
            for cod, val in sorted(contas.items()):
                if val == 0:
                    continue
                det.append({"Descrição": f"    {_desc_por_codigo.get(cod, cod)}",
                            "Valor (R$)": _fmt_br(val)})
        if sp == "1." and dfc.ar != 0:
            det.append({"Descrição": "    Ajuste Receita (AR)",
                        "Valor (R$)": _fmt_br(dfc.ar)})
        if sp == "3." and dfc.ad != 0:
            det.append({"Descrição": "    Ajuste Despesa (AD)",
                        "Valor (R$)": _fmt_br(dfc.ad)})
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

_plot_bg  = "#0F1B35" if _dark else "white"
_grid_clr = "#1E3060" if _dark else "#eee"
_axis_clr = "#8FA0C0" if _dark else "#444"

fig.update_layout(
    height=420,
    margin=dict(t=30, b=10, l=10, r=10),
    plot_bgcolor=_plot_bg,
    paper_bgcolor=_plot_bg,
    yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor=_grid_clr, color=_axis_clr),
    xaxis=dict(color=_axis_clr),
    font=dict(color=_axis_clr),
    showlegend=False,
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Exportar ──────────────────────────────────────────────────────────────────
st.subheader("📤 Exportar")

@st.cache_data(ttl=60)
def _evolucao_para_export(ano: int, meses: tuple):
    """Carrega evolução anual para exportação (mesma lógica da página Evolução)."""
    from core.dfc import calcular_dfc
    rows = []
    for m in meses:
        p = db.carregar_plano_contas(m, ano)
        a = db.carregar_ajustes(m, ano)
        s = db.carregar_saldos(m, ano)
        if p.empty:
            continue
        d = calcular_dfc(p, ar=a["AR"], ad=a["AD"], saldo_banco=s["saldo_banco"])
        rows.append({
            "mes":       m,
            "label":     MESES_ABREV[m],
            "receitas":  d.total_receitas,
            "custos":    abs(d.total_custos),
            "despesas":  abs(d.total_despesas),
            "impostos":  abs(d.total_impostos),
            "saidas":    abs(d.total_custos) + abs(d.total_despesas) + abs(d.total_impostos),
            "resultado": d.resultado_liquido,
        })
    import pandas as _pd
    return _pd.DataFrame(rows)

col_ex1, col_ex2 = st.columns(2)

with col_ex1:
    st.markdown("**📊 Excel — DFC + Evolução**")
    st.caption("Planilha com o DFC do mês selecionado e o comparativo de todos os meses do ano.")
    if st.button("⬇️ Baixar Excel", use_container_width=True):
        with st.spinner("Gerando Excel..."):
            ev_df = _evolucao_para_export(ano, tuple(meses_com_dados))
            excel_bytes = gerar_excel(mes, ano, dfc, plano_df, ev_df)
        st.download_button(
            label="📥 Clique para baixar o arquivo",
            data=excel_bytes,
            file_name=f"CPD_DFC_{MESES_ABREV[mes]}{ano}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

with col_ex2:
    st.markdown("**📄 PDF Executivo — para os CEOs**")
    st.caption("Relatório com KPIs acumulados, gráficos de desempenho e análise de custos de eventos.")
    if st.button("⬇️ Gerar PDF", use_container_width=True):
        with st.spinner("Gerando PDF..."):
            ev_df = _evolucao_para_export(ano, tuple(meses_com_dados))
            pdf_bytes = gerar_pdf_ceo(ano, ev_df, dfc, mes)
        st.download_button(
            label="📥 Clique para baixar o PDF",
            data=pdf_bytes,
            file_name=f"CPD_Relatorio_Executivo_{ano}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
