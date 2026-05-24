"""
Página: Conciliação
Compara lançamentos do Sponte com o extrato bancário.
"""
import streamlit as st
import pandas as pd
import db.client as db
from core.parser import MESES_ABREV

st.title("🔍 Conciliação")
st.markdown("Compare os lançamentos do Sponte com as transações do extrato bancário.")

# ── Seleção de mês ────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 3])
with col1:
    ano = st.selectbox("Ano", [2026, 2025])
meses_com_dados = db.meses_com_dados(ano)
if not meses_com_dados:
    st.info("Nenhum mês importado. Use **📥 Importar Mês** para começar.")
    st.stop()
with col2:
    mes = st.selectbox(
        "Mês", meses_com_dados,
        format_func=lambda m: f"{MESES_ABREV[m]}/{ano}",
        index=len(meses_com_dados) - 1,
    )

# ── Carrega dados ─────────────────────────────────────────────────────────────
sponte_df = db.carregar_lancamentos_sponte(mes, ano)
banco_df  = db.carregar_transacoes_banco(mes, ano)

if sponte_df.empty or banco_df.empty:
    st.warning("Dados de lançamentos não encontrados para este mês.")
    st.stop()

# ── Chave de conciliação ──────────────────────────────────────────────────────
# Chave: DD/MM/YYYY|E/S|valor  (mesmo formato da fórmula Excel)
def make_key_sponte(row):
    d = row["data"]
    data_str = f"{d.day:02d}/{d.month:02d}/{d.year}"
    return f"{data_str}|{row['es']}|{row['valor']:.2f}".replace(".", ",")

def make_key_banco(row):
    data_str = row["data_mov"]
    # data_mov vem como YYYYMMDD do banco
    try:
        from datetime import datetime as dt
        d = dt.strptime(str(data_str), "%Y%m%d")
        data_str = f"{d.day:02d}/{d.month:02d}/{d.year}"
    except Exception:
        pass
    es = "E" if row["deb_cred"] == "C" else "S"
    valor_aj = row["valor"] if row["deb_cred"] == "C" else -row["valor"]
    return f"{data_str}|{es}|{abs(valor_aj):.2f}".replace(".", ",")

sponte_df = sponte_df.copy()
banco_df  = banco_df.copy()

sponte_df["chave"] = sponte_df.apply(make_key_sponte, axis=1)
banco_df["chave"]  = banco_df.apply(make_key_banco, axis=1)

chaves_banco  = set(banco_df["chave"])
chaves_sponte = set(sponte_df["chave"])

sponte_df["status"] = sponte_df["chave"].apply(
    lambda k: "✅ Ok" if k in chaves_banco else "⚠️ Verificar"
)
banco_df["status"] = banco_df["chave"].apply(
    lambda k: "✅ Ok" if k in chaves_sponte else "⚠️ Verificar"
)

# ── Métricas ──────────────────────────────────────────────────────────────────
ok_sp  = (sponte_df["status"] == "✅ Ok").sum()
nok_sp = (sponte_df["status"] == "⚠️ Verificar").sum()
ok_bk  = (banco_df["status"]  == "✅ Ok").sum()
nok_bk = (banco_df["status"]  == "⚠️ Verificar").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Sponte — Ok",        ok_sp,  delta=None)
c2.metric("Sponte — Verificar", nok_sp, delta=f"-{nok_sp}" if nok_sp else None,
          delta_color="inverse" if nok_sp else "off")
c3.metric("Banco — Ok",         ok_bk,  delta=None)
c4.metric("Banco — Verificar",  nok_bk, delta=f"-{nok_bk}" if nok_bk else None,
          delta_color="inverse" if nok_bk else "off")

st.divider()

# ── Filtro ────────────────────────────────────────────────────────────────────
filtro = st.radio(
    "Exibir", ["Todos", "Somente Verificar", "Somente Ok"],
    horizontal=True,
)

def aplicar_filtro(df):
    if filtro == "Somente Verificar":
        return df[df["status"] == "⚠️ Verificar"]
    if filtro == "Somente Ok":
        return df[df["status"] == "✅ Ok"]
    return df

tab1, tab2 = st.tabs([
    f"📋 FluxoCaixa Sponte ({len(sponte_df)})",
    f"🏦 Extrato CEF ({len(banco_df)})",
])

with tab1:
    df_show = aplicar_filtro(sponte_df)[
        ["status", "data", "categoria", "es", "origem_destino", "valor"]
    ].rename(columns={
        "status": "Status", "data": "Data", "categoria": "Categoria",
        "es": "E/S", "origem_destino": "Origem/Destino", "valor": "Valor (R$)",
    })
    st.dataframe(df_show, use_container_width=True, height=500, hide_index=True)

with tab2:
    df_show = aplicar_filtro(banco_df)[
        ["status", "data_mov", "historico", "deb_cred", "valor"]
    ].rename(columns={
        "status": "Status", "data_mov": "Data", "historico": "Histórico",
        "deb_cred": "D/C", "valor": "Valor (R$)",
    })
    st.dataframe(df_show, use_container_width=True, height=500, hide_index=True)
