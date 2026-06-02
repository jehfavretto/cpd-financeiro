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
    parse_caixa_xlsx,
    parse_sponte_plano,
    detectar_mes_ano,
    MESES_ABREV,
)
import db.client as db
from core.utils import fmt_br


st.title("📥 Importar Mês")
st.caption("parser v4 · 30/05/2026")

# ── Contador para resetar os uploaders ───────────────────────────────────────
if "upload_cnt" not in st.session_state:
    st.session_state["upload_cnt"] = 0
_cnt = st.session_state["upload_cnt"]

_header, _btn_col = st.columns([8, 1])
_header.markdown("Faça o upload dos arquivos exportados do Sponte e da CEF para processar o mês.")
if _btn_col.button("✕ Limpar", help="Remover todos os arquivos enviados"):
    st.session_state["upload_cnt"] += 1
    st.rerun()

# ── Upload ────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("**1. Fluxo de Caixa (Sponte)**")
    arquivo_sponte = st.file_uploader(
        "Arquivo .xls do Sponte", type=["xls", "xlsx"], key=f"sponte_{_cnt}"
    )

with col2:
    st.markdown("**2. Extrato CEF**")
    arquivo_banco = st.file_uploader(
        "Arquivo .txt ou .xlsx do banco", type=["txt", "csv", "xlsx", "xls"], key=f"banco_{_cnt}"
    )

with col3:
    st.markdown("**3. Plano de Contas (Sponte)**")
    arquivo_plano = st.file_uploader(
        "Arquivo .xls do Plano de Contas", type=["xls", "xlsx"], key=f"plano_{_cnt}"
    )

with col4:
    st.markdown("**4. Caixa** _(opcional)_")
    arquivo_caixa = st.file_uploader(
        "Planilha de caixa físico (.xlsx)", type=["xlsx", "xls"],
        key=f"caixa_{_cnt}",
        help="Colunas: Data | Descrição | Valor | E/S",
    )

st.divider()

# ── Processa quando todos os arquivos estiverem presentes ────────────────────
if not arquivo_sponte or not arquivo_banco or not arquivo_plano:
    st.info("Faça o upload dos 3 arquivos para continuar.")
    st.stop()

# Lê e valida arquivos
with st.spinner("Lendo arquivos..."):
    try:
        import io as _io, re as _re
        sponte_df = parse_sponte_fluxo(arquivo_sponte)
        nome_banco = arquivo_banco.name.lower()
        arquivo_banco.seek(0)
        _banco_bytes = arquivo_banco.read()

        if nome_banco.endswith(".xlsx") or nome_banco.endswith(".xls"):
            # Parse XLSX inline — evita cache de módulo no servidor
            _DEPARA = {
                "APLICACAO FDO - CLIENTE":   "Aplicação Financeira",
                "MENSALIDADE CESTA SERVICO": "Tarifa Bancária",
                "DEPOSITO DINH LOTERICO":    "Depósito Lotérico",
                "COMPRA CARTAO DEBITO":      "Cartão de Débito",
                "PAG BOLETO IBC":            "Pagamento Boleto",
                "PAGAMENTO TELEFONE IBC":    "Telefone",
            }
            _MINUSC2 = {"de","da","do","dos","das","e","em","na","no","nas","nos","a","o","as","os"}

            def _title_br2(s):
                words = str(s).strip().split()
                return " ".join(
                    w.capitalize() if (i == 0 or w.lower() not in _MINUSC2) else w.lower()
                    for i, w in enumerate(words)
                )

            def _limpar_nome2(nome):
                nome = str(nome).strip()
                if not nome or nome.lower() == "nan":
                    return ""
                nome = _re.sub(r'^[\d\s]+(?=[A-Za-z])', '', nome).strip()
                return _title_br2(nome) if nome.isupper() else nome

            def _parse_val2(v):
                if isinstance(v, (int, float)):
                    return float(v)
                s = str(v).strip()
                if not s or s.lower() == "nan":
                    return 0.0
                negative = "-" in s or "−" in s
                digits = _re.sub(r"[^\d,.]", "", s)
                if not digits:
                    return 0.0
                if "," in digits:
                    digits = digits.replace(".", "").replace(",", ".")
                try:
                    return -float(digits) if negative else float(digits)
                except ValueError:
                    return 0.0

            _r = pd.read_excel(_io.BytesIO(_banco_bytes), dtype=str)
            _r.columns = _r.iloc[0]
            _r = _r.iloc[1:].reset_index(drop=True)
            _r = _r[_r["Histórico"] != "SALDO DIA"].copy()
            _r["data_mov"] = pd.to_datetime(
                _r["Data Lancamento"], format="%d/%m/%Y", errors="coerce"
            ).dt.strftime("%d/%m/%Y").fillna(_r["Data Lancamento"])
            _r["nr_doc"]   = _r["Documento"].fillna("").str.strip()
            _r["historico"] = _r["Histórico"].str.strip()
            _r["_vs"]      = _r["Valor Lançamento"].apply(_parse_val2)
            _r["valor_num"] = _r["_vs"].abs()
            _r["deb_cred"]  = _r["_vs"].apply(lambda v: "S" if v < 0 else "E")
            _r["origem_destino"] = _r.apply(
                lambda row: _limpar_nome2(row.get("Nome/Razão Social", ""))
                            or _DEPARA.get(str(row["historico"]).strip(), str(row["historico"]).strip()),
                axis=1
            )
            banco_df = _r[["data_mov","nr_doc","historico","valor_num","deb_cred","origem_destino"]].reset_index(drop=True)
        else:
            banco_df = parse_banco_txt(_io.BytesIO(_banco_bytes))

        plano_df  = parse_sponte_plano(arquivo_plano)
    except Exception as e:
        st.error(f"Erro ao ler arquivos: {e}")
        st.stop()

# Caixa (opcional — parse separado para não bloquear os 3 obrigatórios)
caixa_df = None
if arquivo_caixa:
    try:
        caixa_df = parse_caixa_xlsx(arquivo_caixa)
    except Exception as e:
        st.warning(f"⚠️ Planilha de caixa ignorada: {e}")

mes, ano = detectar_mes_ano(sponte_df)
mes_nome = MESES_ABREV[mes]

# ── Resumo do que será importado ─────────────────────────────────────────────
st.subheader(f"Mês detectado: {mes_nome}/{ano}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Lançamentos Sponte", len(sponte_df))
col2.metric("Transações Banco",   len(banco_df))
col3.metric("Contas PlanoDeContas", len(plano_df[plano_df["valor"] > 0]))
col4.metric("Lançamentos Caixa", len(caixa_df) if caixa_df is not None else "—")

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

if caixa_df is not None:
    with st.expander("💵 Preview — Caixa Físico", expanded=False):
        c1, c2 = st.columns(2)
        c1.metric("Entradas", fmt_br(caixa_df[caixa_df["deb_cred"]=="E"]["valor"].sum()))
        c2.metric("Saídas",   fmt_br(caixa_df[caixa_df["deb_cred"]=="S"]["valor"].sum()))
        st.dataframe(caixa_df, use_container_width=True, height=250)

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
            if caixa_df is not None:
                db.salvar_lancamentos_caixa(mes, ano, caixa_df)
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            st.stop()

    caixa_info = f"\n- {len(caixa_df)} lançamentos de caixa" if caixa_df is not None else ""
    st.success(
        f"✅ **{mes_nome}/{ano} importado com sucesso!**\n\n"
        f"- {len(sponte_df)} lançamentos do Sponte\n"
        f"- {len(banco_df)} transações do banco\n"
        f"- {len(plano_df)} contas do PlanoDeContas"
        f"{caixa_info}\n\n"
        f"Acesse o **DFC / Resumo** para ver o resultado do mês."
    )
    st.balloons()


