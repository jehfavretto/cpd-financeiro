"""
Página: Relatórios
Exportação de relatórios financeiros — Excel e PDF executivo.
"""
import streamlit as st
from core.dfc import calcular_dfc, SECOES
import db.client as db
from core.parser import MESES_ABREV
from core.exportar import gerar_excel, gerar_pdf_ceo

st.title("📁 Relatórios")

# ── Seleção de período ────────────────────────────────────────────────────────
anos_disponiveis = [2026, 2025]
col1, col2 = st.columns([1, 3])
with col1:
    _ano_saved = st.session_state.get("rel_ano_val", anos_disponiveis[0])
    _ano_idx   = anos_disponiveis.index(_ano_saved) if _ano_saved in anos_disponiveis else 0
    ano = st.selectbox("Ano", anos_disponiveis, index=_ano_idx)
    st.session_state["rel_ano_val"] = ano

meses_com_dados = db.meses_com_dados(ano)
if not meses_com_dados:
    st.info("Nenhum mês importado ainda. Use **📥 Importar Mês** para começar.")
    st.stop()

with col2:
    mes_opcoes = {m: f"{MESES_ABREV[m]}/{ano}" for m in meses_com_dados}
    _mes_list  = list(mes_opcoes.keys())
    _mes_saved = st.session_state.get("rel_mes_val")
    _mes_idx   = _mes_list.index(_mes_saved) if _mes_saved in _mes_list else len(_mes_list) - 1
    mes = st.selectbox("Mês", _mes_list, format_func=lambda m: mes_opcoes[m], index=_mes_idx)
    st.session_state["rel_mes_val"] = mes

# ── Carrega dados ─────────────────────────────────────────────────────────────
plano_df = db.carregar_plano_contas(mes, ano)
ajustes  = db.carregar_ajustes(mes, ano)
saldos   = db.carregar_saldos(mes, ano)

if plano_df.empty:
    st.warning("Dados não encontrados para este mês.")
    st.stop()

dfc = calcular_dfc(plano_df, ar=ajustes["AR"], ad=ajustes["AD"],
                   saldo_banco=saldos["saldo_banco"])

st.divider()

# ── Exportar ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _evolucao_para_export(ano: int, meses: tuple):
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
    st.markdown("**Excel — DFC + Evolução**")
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
    st.markdown("**PDF Executivo — para os CEOs**")
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
