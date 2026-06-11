"""
Página: DFC / Resumo
Demonstração de Fluxo de Caixa — DRE Gerencial + DFC Real validado pela conciliação.
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
anos_disponiveis = [2026, 2025]
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
plano_df = db.carregar_plano_contas(mes, ano)
ajustes  = db.carregar_ajustes(mes, ano)
saldos   = db.carregar_saldos(mes, ano)

if plano_df.empty:
    st.warning("PlanoDeContas não encontrado para este mês.")
    st.stop()

_rendimento_aplic = float(saldos.get("rendimento_aplicacao") or 0.0)
_resgate_aplic    = float(saldos.get("resgate_aplicacao") or 0.0)

dfc = calcular_dfc(
    plano_df,
    ar=ajustes["AR"],
    ad=ajustes["AD"],
    saldo_anterior=saldos.get("saldo_anterior", 0.0),
    saldo_banco=saldos["saldo_banco"],
    saldo_aplicacao=saldos["saldo_aplicacao"],
    saldo_caixa=saldos["saldo_caixa"],
)

# ── Cores dinâmicas conforme o tema ──────────────────────────────────────────
_dark      = st.session_state.get("tema", "light") == "dark"
_card      = "#1A2550" if _dark else "#f8f9fb"
_txt       = "#E8EDF6" if _dark else "#1C2B5F"
_txt2      = "#8FA0C0" if _dark else "#555555"
_accent    = "#E63A5C" if _dark else "#C4153A"
_br        = fmt_br_kpi
_border_c  = "rgba(232,237,246,0.12)" if _dark else "#e5e7eb"
_th_border = "rgba(232,237,246,0.25)" if _dark else "#d1d5db"
_pos_c     = "#2ed64f" if _dark else "#1a7f37"
_neg_c     = "#E63A5C" if _dark else "#C4153A"

# ── KPIs principais (comuns às duas abas) ────────────────────────────────────
st.subheader(f"{MESES_ABREV[mes]}/{ano}")

resultado  = dfc.resultado_liquido
res_color  = ("#2ed64f" if _dark else "#1a7f37") if resultado >= 0 else _accent
res_bg     = ("#0d2a1a" if _dark else "#eaffea") if resultado >= 0 else ("#2a0d14" if _dark else "#fff0f0")
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

# ── Abas DRE / DFC ───────────────────────────────────────────────────────────
tab_dre, tab_dfc = st.tabs(["📊 DRE — Resultado Gerencial", "💰 DFC — Fluxo de Caixa Real"])

# ════════════════════════════════════════════════════════════════════════════
# ABA DRE
# ════════════════════════════════════════════════════════════════════════════
with tab_dre:

    # ── Ajustes manuais (AR / AD) ─────────────────────────────────────────
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

    # ── Demonstração: resumo compacto + analítico retrátil ────────────────
    st.subheader("Demonstração")

    _desc_por_codigo = dict(zip(plano_df["codigo"], plano_df["descricao"]))
    _fmt_br = fmt_br

    sec_totals = {}
    for sp, si in SECOES.items():
        t = dfc.total_secao(sp)
        if sp == "1.":
            t += dfc.ar
        if sp == "3.":
            t += dfc.ad
        sec_totals[sp] = t

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
    _dre_rows = ""
    for r in resumo:
        _desc = r["Seção"]
        _val  = r["Valor (R$)"]
        _bold = "font-weight:700;" if _desc in ("RESULTADO LÍQUIDO",) else ""
        _color = f"color:{('#2ed64f' if _dark else '#1a7f37')};" if (_bold and "-" not in _val) else (f"color:{('#E63A5C' if _dark else '#C4153A')};" if (_bold and "-" in _val) else "")
        _dre_rows += (
            f"<tr>"
            f"<td style='padding:4px 12px;border-bottom:1px solid {_border_c};color:{_txt};{_bold}'>{_desc}</td>"
            f"<td style='padding:4px 12px;border-bottom:1px solid {_border_c};text-align:left;color:{_txt};{_bold}{_color}'>{_val}</td>"
            f"</tr>"
        )
    st.markdown(f"""
<table style='width:100%;border-collapse:collapse;font-size:0.9rem;background:transparent;'>
  <thead>
    <tr style='background:{"transparent" if _dark else "#f3f4f6"};'>
      <th style='padding:4px 12px;text-align:left;font-weight:600;border-bottom:2px solid {_th_border};color:{_txt};'>Seção</th>
      <th style='padding:4px 12px;text-align:left;font-weight:600;border-bottom:2px solid {_th_border};color:{_txt};'>Valor (R$)</th>
    </tr>
  </thead>
  <tbody>{_dre_rows}</tbody>
</table>
""", unsafe_allow_html=True)

    for sp, si in SECOES.items():
        with st.expander(f"{si['label']}  —  {_fmt_br(sec_totals[sp])}"):
            det = []
            for grp_prefix, grp_label in {k: v for k, v in GRUPOS.items() if k.startswith(sp[0])}.items():
                contas = dfc.dados.get(sp, {}).get(grp_prefix, {})
                grp_total = sum(contas.values())
                if not contas:
                    continue
                det.append({"Descrição": grp_label, "Valor (R$)": _fmt_br(grp_total)})
                for cod, val in sorted(contas.items()):
                    if val == 0:
                        continue
                    det.append({"Descrição": f"    {_desc_por_codigo.get(cod, cod)}",
                                "Valor (R$)": _fmt_br(val)})
            if sp == "1." and dfc.ar != 0:
                det.append({"Descrição": "    Ajuste Receita (AR)", "Valor (R$)": _fmt_br(dfc.ar)})
            if sp == "3." and dfc.ad != 0:
                det.append({"Descrição": "    Ajuste Despesa (AD)", "Valor (R$)": _fmt_br(dfc.ad)})
            if det:
                st.dataframe(pd.DataFrame(det), hide_index=True, use_container_width=True)
            else:
                st.caption("Sem lançamentos nesta seção.")

    st.divider()

    # ── Gráfico Waterfall ─────────────────────────────────────────────────
    st.subheader("📊 Resultado do mês")

    _plot_bg  = "#0F1B35" if _dark else "white"
    _grid_clr = "#1E3060" if _dark else "#eee"
    _axis_clr = "#8FA0C0" if _dark else "#444"

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
        plot_bgcolor=_plot_bg,
        paper_bgcolor=_plot_bg,
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor=_grid_clr, color=_axis_clr),
        xaxis=dict(color=_axis_clr),
        font=dict(color=_axis_clr),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Exportar ──────────────────────────────────────────────────────────
    st.subheader("📤 Exportar")

    @st.cache_data(ttl=60)
    def _evolucao_para_export(ano: int, meses: tuple):
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

# ════════════════════════════════════════════════════════════════════════════
# ABA DFC
# ════════════════════════════════════════════════════════════════════════════
with tab_dfc:
    st.caption("Receitas do Sponte ajustadas pelos motivos da conciliação — deve bater com Banco + Caixa.")

    # ── Saldos de caixa (anterior e atual) para variação ─────────────────
    _mes_ant_dfc = mes - 1 if mes > 1 else 12
    _ano_ant_dfc = ano   if mes > 1 else ano - 1
    _saldos_ant_dfc      = db.carregar_saldos(_mes_ant_dfc, _ano_ant_dfc)
    _saldo_caixa_final   = float(saldos.get("saldo_caixa") or 0.0)
    _saldo_caixa_anterior = float(_saldos_ant_dfc.get("saldo_caixa") or 0.0)
    _variacao_caixa      = _saldo_caixa_final - _saldo_caixa_anterior

    # ── Classifica motivos ────────────────────────────────────────────────
    _DEDUZ       = {"Valor Desviado", "Desconto em folha", "Pagamento não localizado",
                    "Estorno/Cancelamento"}

    def _normalizar_motivo(just):
        s = str(just or "").strip()
        for emoji in ["🚨 ", "📝 ", "💵 ", "❓ ", "↩️ "]:
            if s.startswith(emoji):
                s = s[len(emoji):]
        return s

    def _valor_da_chave(chave):
        try:
            parts = str(chave).split("|")
            if len(parts) >= 3:
                return float(parts[2].replace(",", "."))
        except:
            pass
        return 0.0

    # ── Carrega conciliações do mês ───────────────────────────────────────
    conciliacoes = db.carregar_conciliacoes(mes, ano)
    ignorados_sp = [c for c in conciliacoes if c["tipo"] == "ignorado_sponte"]

    _deducoes = {}
    for c in ignorados_sp:
        mot = _normalizar_motivo(c.get("justificativa", ""))
        val = _valor_da_chave(c.get("sponte_chave", ""))
        if mot in _DEDUZ:
            _deducoes[mot] = _deducoes.get(mot, 0.0) + val

    # Itens ignorados do banco — separados entre saídas (aplicação) e entradas extras
    _BANCO_SAIDA  = {"Aplicação Financeira"}
    ignorados_bk  = [c for c in conciliacoes if c["tipo"] == "ignorado_banco"]
    _extras_banco = {}
    _saidas_banco = {}
    for c in ignorados_bk:
        mot = _normalizar_motivo(c.get("justificativa", ""))
        val = _valor_da_chave(c.get("banco_chave", ""))
        if val > 0:
            if mot in _BANCO_SAIDA:
                _saidas_banco[mot] = _saidas_banco.get(mot, 0.0) + val
            else:
                _extras_banco[mot] = _extras_banco.get(mot, 0.0) + val

    _receitas_sponte = dfc.total_receitas
    _saidas_sponte   = dfc.total_custos + dfc.total_despesas + dfc.total_impostos
    _diferenca_caixa = float(saldos.get("diferenca_caixa") or 0.0)

    _total_extras    = sum(_extras_banco.values()) - sum(_saidas_banco.values())
    _total_deducoes  = sum(_deducoes.values())
    _receitas_reais  = _receitas_sponte - _total_deducoes
    _resultado_caixa = _receitas_reais + _total_extras + _resgate_aplic + _saidas_sponte - _diferenca_caixa

    # ── KPIs DFC ──────────────────────────────────────────────────────────
    _rc_color = ("#2ed64f" if _dark else "#1a7f37") if _resultado_caixa >= 0 else _accent
    _rc_bg    = ("#0d2a1a" if _dark else "#eaffea") if _resultado_caixa >= 0 else ("#2a0d14" if _dark else "#fff0f0")

    st.markdown(f"""
<div style="display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap;">
  <div style="flex:1; min-width:140px; background:{_card}; border-left:4px solid {_txt};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">📈 Receitas Sponte</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_txt};">{_br(_receitas_sponte)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:{_card}; border-left:4px solid {_accent};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">➖ Deduções Sponte</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_accent};">{_br(_total_deducoes)}</div>
  </div>
  <div style="flex:1; min-width:140px; background:{_card}; border-left:4px solid #2A9D8F;
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">➕ Extras Banco</div>
    <div style="font-size:1.35rem; font-weight:700; color:#2A9D8F;">{_br(_total_extras + _resgate_aplic)}</div>
  </div>
  <div style="flex:1.2; min-width:160px; background:{_rc_bg}; border-left:4px solid {_rc_color};
              border-radius:6px; padding:14px 16px;">
    <div style="font-size:0.78rem; color:{_txt2}; margin-bottom:4px;">💰 Resultado do Mês</div>
    <div style="font-size:1.35rem; font-weight:700; color:{_rc_color};">{_br(_resultado_caixa)}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.divider()

    # ── Tabela detalhada ──────────────────────────────────────────────────
    st.subheader("Demonstração")
    _linhas = []
    _linhas.append({"Descrição": "📈 Receitas (Sponte)",              "Valor (R$)": fmt_br(_receitas_sponte)})
    for mot, val in _deducoes.items():
        _linhas.append({"Descrição": f"    ➖ {mot}",                 "Valor (R$)": fmt_br(-val)})
    _linhas.append({"Descrição": "= Receitas Reais",                  "Valor (R$)": fmt_br(_receitas_reais)})
    for mot, val in _extras_banco.items():
        _linhas.append({"Descrição": f"    ➕ {mot} (Banco)",          "Valor (R$)": fmt_br(val)})
    for mot, val in _saidas_banco.items():
        _linhas.append({"Descrição": f"    ➖ {mot} (Banco)",          "Valor (R$)": fmt_br(-val)})
    if _resgate_aplic:
        _linhas.append({"Descrição": "    ➕ Resgate da Aplicação",    "Valor (R$)": fmt_br(_resgate_aplic)})
    if _diferenca_caixa != 0:
        _linhas.append({"Descrição": "    ⚖️ Diferença Sponte/Caixa", "Valor (R$)": fmt_br(-_diferenca_caixa)})
    _linhas.append({"Descrição": "🏭 Custos",                         "Valor (R$)": fmt_br(dfc.total_custos)})
    _linhas.append({"Descrição": "🏢 Despesas",                       "Valor (R$)": fmt_br(dfc.total_despesas)})
    _linhas.append({"Descrição": "🏛️ Impostos",                       "Valor (R$)": fmt_br(dfc.total_impostos)})
    _linhas.append({"Descrição": "= RESULTADO DO MÊS",                 "Valor (R$)": fmt_br(_resultado_caixa)})
    _th_bg  = "transparent" if _dark else "#f3f4f6"
    _rows_html = ""
    for l in _linhas:
        _desc = l["Descrição"]
        _val  = l["Valor (R$)"]
        _bold = "font-weight:700;" if _desc.startswith("=") else ""
        _color = f"color:{_neg_c};" if (_desc.startswith("=") and "-" in _val) else (f"color:{_pos_c};" if _desc.startswith("=") else "")
        _rows_html += (
            f"<tr>"
            f"<td style='padding:4px 12px;border-bottom:1px solid {_border_c};color:{_txt};{_bold}'>{_desc}</td>"
            f"<td style='padding:4px 12px;border-bottom:1px solid {_border_c};text-align:left;color:{_txt};{_bold}{_color}'>{_val}</td>"
            f"</tr>"
        )
    st.markdown(f"""
<table style='width:100%;border-collapse:collapse;font-size:0.9rem;background:transparent;'>
  <thead>
    <tr style='background:{_th_bg};'>
      <th style='padding:4px 12px;text-align:left;font-weight:600;border-bottom:2px solid {_th_border};color:{_txt};'>Descrição</th>
      <th style='padding:4px 12px;text-align:left;font-weight:600;border-bottom:2px solid {_th_border};color:{_txt};'>Valor (R$)</th>
    </tr>
  </thead>
  <tbody>{_rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

    st.divider()

    # ── Conferência com Banco + Caixa ─────────────────────────────────────
    st.subheader("📋 Conferência")

    _saldo_banco_final = float(saldos.get("saldo_banco") or 0.0)
    _saldo_caixa_final = float(saldos.get("saldo_caixa") or 0.0)
    _saldo_real        = _saldo_banco_final + _saldo_caixa_final

    # Reutiliza saldo anterior já carregado no início da aba DFC
    _mes_ant  = _mes_ant_dfc
    _ano_ant  = _ano_ant_dfc
    _saldos_ant = _saldos_ant_dfc
    _saldo_ant_auto = float(_saldos_ant.get("saldo_banco") or 0.0) + float(_saldos_ant.get("saldo_caixa") or 0.0)

    # Se não encontrou saldo anterior, permite informar manualmente
    _chave_ant = f"saldo_ant_{mes}_{ano}"
    if _saldo_ant_auto == 0.0:
        st.caption(f"⚠️ Saldo de {MESES_ABREV[_mes_ant]}/{_ano_ant} não encontrado — informe manualmente:")
        _ja_salvo = _chave_ant in st.session_state and st.session_state[_chave_ant] > 0

        if _ja_salvo:
            # Mostra valor travado com botão de editar
            _col_val, _col_btn, _col_rest = st.columns([2, 1, 6])
            _col_val.text_input(
                f"Saldo {MESES_ABREV[_mes_ant]}/{_ano_ant} (R$)",
                value=st.session_state.get(f"txt_{_chave_ant}", ""),
                disabled=True,
                key=f"txt_dis_{_chave_ant}",
            )
            with _col_btn:
                st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                if st.button("✏️ Editar", key=f"btn_edit_{_chave_ant}"):
                    del st.session_state[_chave_ant]
                    st.rerun()
        else:
            # Mostra campo editável + botão Aplicar
            _col_inp, _col_btn, _col_rest = st.columns([2, 1, 8])
            with _col_inp:
                _txt_ant = st.text_input(
                    f"Saldo {MESES_ABREV[_mes_ant]}/{_ano_ant} (R$)",
                    value=st.session_state.get(f"txt_{_chave_ant}", ""),
                    placeholder="ex: 11.728,30",
                    key=f"txt_{_chave_ant}",
                )
            with _col_btn:
                st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                if st.button("✔ ok", key=f"btn_{_chave_ant}"):
                    _raw = st.session_state.get(f"txt_{_chave_ant}", "") or ""
                    try:
                        _v = _raw.strip().replace(" ", "").replace("R$", "").replace("\xa0", "")
                        if not _v:
                            st.warning("Digite um valor antes de aplicar.")
                        else:
                            # aceita: 11728,30 / 11.728,30 / 11728.30
                            if "," in _v and "." in _v:
                                _v = _v.replace(".", "").replace(",", ".")
                            elif "," in _v:
                                _v = _v.replace(",", ".")
                            _val_parsed = float(_v)
                            st.session_state[_chave_ant] = _val_parsed
                            # salva no banco para persistir entre sessões
                            _sa = db.carregar_saldos(_mes_ant, _ano_ant)
                            db.salvar_saldos(
                                _mes_ant, _ano_ant,
                                _val_parsed,
                                float(_sa.get("saldo_aplicacao") or 0.0),
                                float(_sa.get("saldo_caixa") or 0.0),
                                rendimento_aplicacao=float(_sa.get("rendimento_aplicacao") or 0.0),
                                resgate_aplicacao=float(_sa.get("resgate_aplicacao") or 0.0),
                            )
                            st.rerun()
                    except Exception as _e:
                        st.warning(f"Valor inválido: '{_raw}'. Use formato 11728,30 ou 11.728,30")
        _saldo_ant = st.session_state.get(_chave_ant, 0.0)
    else:
        _saldo_ant = _saldo_ant_auto

    _saldo_calc = _saldo_ant + _resultado_caixa
    _diferenca  = _saldo_real - _saldo_calc

    _conf = [
        {"":  f"Saldo banco + caixa anterior ({MESES_ABREV[_mes_ant]}/{_ano_ant})", "Valor (R$)": fmt_br(_saldo_ant)},
        {"":  "+ Resultado do mês",              "Valor (R$)": fmt_br(_resultado_caixa)},
        {"":  "= Saldo calculado",              "Valor (R$)": fmt_br(_saldo_calc)},
        {"":  "Saldo real (banco + caixa)",     "Valor (R$)": fmt_br(_saldo_real)},
        {"":  "Diferença",                      "Valor (R$)": fmt_br(_diferenca)},
    ]
    _conf_html = ""
    for row in _conf:
        _desc = row[""]
        _val  = row["Valor (R$)"]
        _bold = "font-weight:700;" if _desc.startswith("=") else ""
        _color = f"color:{_neg_c};" if ("-" in _val and _desc.startswith("=")) else (f"color:{_pos_c};" if (_desc.startswith("=") and "-" not in _val) else "")
        _conf_html += (
            f"<tr>"
            f"<td style='padding:4px 12px;border-bottom:1px solid {_border_c};color:{_txt};{_bold}'>{_desc}</td>"
            f"<td style='padding:4px 12px;border-bottom:1px solid {_border_c};text-align:left;color:{_txt};{_bold}{_color}'>{_val}</td>"
            f"</tr>"
        )
    st.markdown(f"""
<table style='width:100%;border-collapse:collapse;font-size:0.9rem;background:transparent;'>
  <thead>
    <tr style='background:{_th_bg};'>
      <th style='padding:4px 12px;text-align:left;font-weight:600;border-bottom:2px solid {_th_border};color:{_txt};'></th>
      <th style='padding:4px 12px;text-align:left;font-weight:600;border-bottom:2px solid {_th_border};color:{_txt};'>Valor (R$)</th>
    </tr>
  </thead>
  <tbody>{_conf_html}</tbody>
</table>
""", unsafe_allow_html=True)

    if abs(_diferenca) < 0.01:
        st.success("✅ DFC confere com o saldo real de banco + caixa!")
    else:
        st.warning(f"⚠️ Diferença de {fmt_br(abs(_diferenca))} — verifique se há itens não conciliados ou saldos incorretos.")
