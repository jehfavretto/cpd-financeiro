"""
Página: Importar Mês
Upload dos 3 arquivos → processamento → gravação no Supabase.
"""
import streamlit as st
import pandas as pd
from core.parser import (
    parse_sponte_fluxo,
    parse_banco_txt,
    parse_banco_xlsx,
    parse_sponte_plano,
    detectar_mes_ano,
    MESES_ABREV,
)
import db.client as db
from core.utils import fmt_br


st.title("📥 Importar Mês")
st.markdown("Faça o upload dos arquivos exportados do Sponte e da CEF para processar o mês.")

# ── Upload ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**1. FluxoCaixa (Sponte)**")
    arquivo_sponte = st.file_uploader(
        "Arquivo .xls do Sponte", type=["xls", "xlsx"], key="sponte"
    )

with col2:
    st.markdown("**2. Extrato CEF**")
    arquivo_banco = st.file_uploader(
        "Arquivo .txt ou .xlsx do banco", type=["txt", "csv", "xlsx", "xls"], key="banco"
    )

with col3:
    st.markdown("**3. PlanoDeContas (Sponte)**")
    arquivo_plano = st.file_uploader(
        "Arquivo .xls do PlanoDeContas", type=["xls", "xlsx"], key="plano"
    )

st.divider()

# ── Processa quando todos os arquivos estiverem presentes ────────────────────
if not arquivo_sponte or not arquivo_banco or not arquivo_plano:
    st.info("Faça o upload dos 3 arquivos para continuar.")
    st.stop()

# Lê e valida arquivos
with st.spinner("Lendo arquivos..."):
    try:
        sponte_df = parse_sponte_fluxo(arquivo_sponte)
        # Detecta formato do extrato: XLSX novo (CEF online) ou TXT antigo
        nome_banco = arquivo_banco.name.lower()
        if nome_banco.endswith(".xlsx") or nome_banco.endswith(".xls"):
            banco_df = parse_banco_xlsx(arquivo_banco)
        else:
            banco_df = parse_banco_txt(arquivo_banco)
        plano_df  = parse_sponte_plano(arquivo_plano)
    except Exception as e:
        st.error(f"Erro ao ler arquivos: {e}")
        st.stop()

mes, ano = detectar_mes_ano(sponte_df)
mes_nome = MESES_ABREV[mes]

# ── Resumo do que será importado ─────────────────────────────────────────────
st.subheader(f"Mês detectado: {mes_nome}/{ano}")

col1, col2, col3 = st.columns(3)
col1.metric("Lançamentos Sponte", len(sponte_df))
col2.metric("Transações Banco",   len(banco_df))
col3.metric("Contas PlanoDeContas", len(plano_df[plano_df["valor"] > 0]))

st.divider()

# ── Preview dos dados ─────────────────────────────────────────────────────────
with st.expander("📋 Preview — FluxoCaixa Sponte", expanded=False):
    entradas = sponte_df[sponte_df["es"] == "E"]["valor"].sum()
    saidas   = sponte_df[sponte_df["es"] == "S"]["valor"].sum()
    c1, c2 = st.columns(2)
    c1.metric("Entradas", fmt_br(entradas))
    c2.metric("Saídas",   fmt_br(saidas))
    st.dataframe(
        sponte_df[["data", "categoria", "es", "origem_destino", "valor"]],
        use_container_width=True, height=250,
    )

with st.expander("🏦 Preview — Extrato CEF", expanded=False):
    entradas_b = banco_df[banco_df["deb_cred"] == "E"]["valor_num"].sum()
    saidas_b   = banco_df[banco_df["deb_cred"] == "S"]["valor_num"].sum()
    c1, c2 = st.columns(2)
    c1.metric("Créditos", fmt_br(entradas_b))
    c2.metric("Débitos",  fmt_br(saidas_b))
    preview_cols = ["data_mov", "historico", "origem_destino", "valor_num", "deb_cred"]
    st.dataframe(
        banco_df[[c for c in preview_cols if c in banco_df.columns]],
        use_container_width=True, height=250,
    )

with st.expander("📑 Preview — PlanoDeContas", expanded=False):
    plano_view = plano_df[plano_df["valor"] > 0].copy()
    st.dataframe(plano_view, use_container_width=True, height=300)

st.divider()

# ── Saldos manuais ────────────────────────────────────────────────────────────
st.subheader("💰 Saldos em {mes_nome}/{ano}".format(mes_nome=mes_nome, ano=ano))
st.markdown(
    "Informe os saldos ao final do mês. "
    "O saldo bancário é calculado automaticamente pelo extrato, mas você pode ajustar."
)

saldo_banco_calc = (
    banco_df[banco_df["deb_cred"] == "E"]["valor_num"].sum()
    - banco_df[banco_df["deb_cred"] == "S"]["valor_num"].sum()
)

c1, c2, c3 = st.columns(3)
with c1:
    saldo_banco = st.number_input(
        "Saldo Banco (R$)", value=float(round(saldo_banco_calc, 2)),
        format="%.2f", step=100.0,
    )
with c2:
    saldo_aplicacao = st.number_input(
        "Saldo Aplicação (R$)", value=0.0, format="%.2f", step=100.0,
    )
with c3:
    saldo_caixa = st.number_input(
        "Saldo Caixa — dinheiro físico (R$)", value=0.0, format="%.2f", step=10.0,
    )

# ── Botão confirmar ───────────────────────────────────────────────────────────
st.divider()

if st.button(f"✅ Confirmar importação de {mes_nome}/{ano}", type="primary", use_container_width=True):
    with st.spinner("Salvando dados..."):
        try:
            db.salvar_lancamentos_sponte(mes, ano, sponte_df)
            db.salvar_transacoes_banco(mes, ano, banco_df)
            db.salvar_plano_contas(mes, ano, plano_df)
            db.salvar_saldos(mes, ano, saldo_banco, saldo_aplicacao, saldo_caixa)
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            st.stop()

    st.success(
        f"✅ **{mes_nome}/{ano} importado com sucesso!**\n\n"
        f"- {len(sponte_df)} lançamentos do Sponte\n"
        f"- {len(banco_df)} transações do banco\n"
        f"- {len(plano_df)} contas do PlanoDeContas\n\n"
        f"Acesse o **DFC / Resumo** para ver o resultado do mês."
    )
    st.balloons()


