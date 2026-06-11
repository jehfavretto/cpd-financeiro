"""
Página: Importar Mês
Upload dos arquivos → processamento → gravação no Supabase.
Todos os arquivos são opcionais — importa só o que for enviado.
"""
import streamlit as st
import pandas as pd
from core.parser import (
    parse_sponte_fluxo,
    parse_banco_txt,
    parse_banco_xlsx,
    parse_caixa_xlsx,
    parse_sponte_plano,
    parse_extrato_fundos_pdf,
    detectar_mes_ano,
    MESES_ABREV,
)
import db.client as db
from core.utils import fmt_br


st.title("📥 Importar Mês")
st.caption("parser v5 · 08/06/2026")

# ── Contador para resetar os uploaders ───────────────────────────────────────
if "upload_cnt" not in st.session_state:
    st.session_state["upload_cnt"] = 0
_cnt = st.session_state["upload_cnt"]

_header, _btn_col = st.columns([8, 1])
_header.markdown("Envie apenas os arquivos que deseja atualizar. Os demais dados do mês serão mantidos.")
if _btn_col.button("✕ Limpar", help="Remover todos os arquivos enviados"):
    st.session_state["upload_cnt"] += 1
    st.rerun()

# ── Upload ────────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

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

with col5:
    st.markdown("**5. Extrato de Fundos** _(opcional)_")
    arquivo_fundos = st.file_uploader(
        "PDF do Extrato de Fundos CEF", type=["pdf"],
        key=f"fundos_{_cnt}",
        help="PDF gerado pelo site da Caixa — preenche Aplicação, Rendimento e Resgate automaticamente",
    )

st.divider()

# ── Exige pelo menos 1 arquivo ────────────────────────────────────────────────
_algum = arquivo_sponte or arquivo_banco or arquivo_plano or arquivo_caixa or arquivo_fundos
if not _algum:
    st.info("Envie pelo menos um arquivo para continuar.")
    st.stop()

# ── Seletor de mês/ano (sempre visível; auto-preenchido se Sponte enviado) ───
_ano_atual = 2026
_MESES_NOMES = [MESES_ABREV[m] for m in range(1, 13)]

# detecta mês/ano do Sponte se disponível
_mes_auto, _ano_auto = None, None
sponte_df = None
if arquivo_sponte:
    try:
        sponte_df = parse_sponte_fluxo(arquivo_sponte)
        _mes_auto, _ano_auto = detectar_mes_ano(sponte_df)
    except Exception as e:
        st.error(f"Erro ao ler Fluxo de Caixa Sponte: {e}")
        st.stop()

_col_mes, _col_ano, _col_info = st.columns([2, 1, 5])
with _col_mes:
    _mes_idx = (_mes_auto - 1) if _mes_auto else 0
    mes_sel_nome = st.selectbox(
        "Mês",
        _MESES_NOMES,
        index=_mes_idx,
        disabled=bool(_mes_auto),
        help="Detectado automaticamente pelo arquivo Sponte" if _mes_auto else "Selecione o mês",
    )
    mes = _MESES_NOMES.index(mes_sel_nome) + 1

with _col_ano:
    ano = st.number_input(
        "Ano",
        min_value=2020,
        max_value=2035,
        value=_ano_auto or _ano_atual,
        step=1,
        disabled=bool(_ano_auto),
        help="Detectado automaticamente pelo arquivo Sponte" if _ano_auto else "Informe o ano",
    )
    ano = int(ano)

mes_nome = MESES_ABREV[mes]

if _mes_auto:
    _col_info.info(f"📅 Mês detectado automaticamente: **{mes_nome}/{ano}**")
else:
    _col_info.warning(f"📅 Mês selecionado manualmente: **{mes_nome}/{ano}** — confirme antes de importar")

# ── Processa arquivos enviados ────────────────────────────────────────────────
import io as _io, re as _re

banco_df   = None
plano_df   = None
caixa_df   = None
fundos_dat = None

if arquivo_banco:
    try:
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
            nome = _re.sub(r'^[\d.\-/\s]+(?=[A-Za-z])', '', nome).strip()
            nome = _re.sub(r'[\s\d\-\.]{6,}$', '', nome).strip()
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

        nome_banco = arquivo_banco.name.lower()
        arquivo_banco.seek(0)
        _banco_bytes = arquivo_banco.read()

        if nome_banco.endswith(".xlsx") or nome_banco.endswith(".xls"):
            _r = pd.read_excel(_io.BytesIO(_banco_bytes), dtype=str)
            _r.columns = _r.iloc[0]
            _r = _r.iloc[1:].reset_index(drop=True)
            _r = _r[_r["Histórico"] != "SALDO DIA"].copy()
            _r["data_mov"] = pd.to_datetime(
                _r["Data Movimento"], dayfirst=True, errors="coerce"
            ).dt.strftime("%d/%m/%Y").fillna(_r["Data Movimento"])
            _r["nr_doc"]    = _r["Documento"].fillna("").str.strip()
            _r["historico"] = _r["Histórico"].str.strip()
            _r["_vs"]       = _r["Valor Lançamento"].apply(_parse_val2)
            _r["valor_num"] = _r["_vs"].abs()
            _r["deb_cred"]  = _r["_vs"].apply(lambda v: "S" if v < 0 else "E")
            _r["origem_destino"] = _r.apply(
                lambda row: _limpar_nome2(row.get("Nome/Razão Social", ""))
                            or _DEPARA.get(str(row["historico"]).strip(), str(row["historico"]).strip()),
                axis=1,
            )
            banco_df = _r[["data_mov","nr_doc","historico","valor_num","deb_cred","origem_destino"]].reset_index(drop=True)
        else:
            banco_df = parse_banco_txt(_io.BytesIO(_banco_bytes))
    except Exception as e:
        st.error(f"Erro ao ler Extrato CEF: {e}")
        st.stop()

if arquivo_plano:
    try:
        plano_df = parse_sponte_plano(arquivo_plano)
    except Exception as e:
        st.error(f"Erro ao ler Plano de Contas: {e}")
        st.stop()

if arquivo_caixa:
    try:
        caixa_df = parse_caixa_xlsx(arquivo_caixa)
    except Exception as e:
        st.warning(f"⚠️ Planilha de caixa ignorada: {e}")

if arquivo_fundos:
    try:
        arquivo_fundos.seek(0)
        fundos_dat = parse_extrato_fundos_pdf(arquivo_fundos.read())
        if fundos_dat.get("mes") and fundos_dat.get("ano"):
            _mes_f = fundos_dat["mes"]
            _ano_f = fundos_dat["ano"]
            if _mes_f != mes or _ano_f != ano:
                st.warning(
                    f"⚠️ O Extrato de Fundos é de **{MESES_ABREV[_mes_f]}/{_ano_f}** "
                    f"mas o mês selecionado é **{mes_nome}/{ano}**. Verifique antes de importar."
                )
    except Exception as e:
        st.warning(f"⚠️ Extrato de Fundos ignorado: {e}")

# ── Resumo do que será importado ─────────────────────────────────────────────
st.subheader(f"Resumo — {mes_nome}/{ano}")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Lançamentos Sponte",    len(sponte_df) if sponte_df is not None else "—")
col2.metric("Transações Banco",      len(banco_df)  if banco_df  is not None else "—")
col3.metric("Contas Plano de Contas",
            len(plano_df[plano_df["valor"] > 0]) if plano_df is not None else "—")
col4.metric("Lançamentos Caixa",     len(caixa_df)  if caixa_df  is not None else "—")
col5.metric("Extrato de Fundos",     "✅ lido" if fundos_dat else "—")

st.divider()

# ── Preview dos dados ─────────────────────────────────────────────────────────
if sponte_df is not None:
    with st.expander("📋 Preview — Fluxo de Caixa Sponte", expanded=False):
        entradas = sponte_df[sponte_df["es"] == "E"]["valor"].sum()
        saidas   = sponte_df[sponte_df["es"] == "S"]["valor"].sum()
        c1, c2 = st.columns(2)
        c1.metric("Entradas", fmt_br(entradas))
        c2.metric("Saídas",   fmt_br(saidas))
        st.dataframe(
            sponte_df[["data", "categoria", "es", "origem_destino", "valor"]],
            use_container_width=True, height=250,
        )

if banco_df is not None:
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

if plano_df is not None:
    with st.expander("📑 Preview — Plano de Contas", expanded=False):
        plano_view = plano_df[plano_df["valor"] > 0].copy()
        st.dataframe(plano_view, use_container_width=True, height=300)

if caixa_df is not None:
    with st.expander("💵 Preview — Caixa Físico", expanded=False):
        c1, c2 = st.columns(2)
        c1.metric("Entradas", fmt_br(caixa_df[caixa_df["deb_cred"]=="E"]["valor"].sum()))
        c2.metric("Saídas",   fmt_br(caixa_df[caixa_df["deb_cred"]=="S"]["valor"].sum()))
        st.dataframe(caixa_df, use_container_width=True, height=250)

if fundos_dat:
    with st.expander("📈 Preview — Extrato de Fundos", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Saldo Anterior",  fmt_br(fundos_dat["saldo_anterior"]))
        c2.metric("Rendimento",      fmt_br(fundos_dat["rendimento"]))
        c3.metric("Aplicações",      fmt_br(fundos_dat["aplicacoes"]))
        c4.metric("Saldo Final",     fmt_br(fundos_dat["saldo_bruto"]))

st.divider()

# ── Saldos automáticos ────────────────────────────────────────────────────────
st.subheader(f"💰 Saldos em {mes_nome}/{ano}")
st.caption("Calculados automaticamente — ajuste se necessário antes de confirmar.")

# Busca saldos do mês anterior para base de cálculo
_mes_ant = mes - 1 if mes > 1 else 12
_ano_ant = ano   if mes > 1 else ano - 1
_saldos_ant = db.carregar_saldos(_mes_ant, _ano_ant)
_banco_ant  = float(_saldos_ant.get("saldo_banco") or 0.0)
_caixa_ant  = float(_saldos_ant.get("saldo_caixa") or 0.0)

# Saldo banco = mês anterior + créditos − débitos do extrato
if banco_df is not None:
    _banco_cred = banco_df[banco_df["deb_cred"] == "E"]["valor_num"].sum()
    _banco_deb  = banco_df[banco_df["deb_cred"] == "S"]["valor_num"].sum()
    _saldo_banco_calc = round(_banco_ant + _banco_cred - _banco_deb, 2)
    _banco_origem = f"calculado: {fmt_br(_banco_ant)} (ant.) + {fmt_br(_banco_cred)} − {fmt_br(_banco_deb)}"
else:
    _saldo_banco_calc = float(db.carregar_saldos(mes, ano).get("saldo_banco") or 0.0)
    _banco_origem = "valor salvo anteriormente"

# Saldo caixa = mês anterior + entradas − saídas dos lançamentos de caixa
if caixa_df is not None:
    _caixa_ent = caixa_df[caixa_df["deb_cred"] == "E"]["valor"].sum()
    _caixa_sai = caixa_df[caixa_df["deb_cred"] == "S"]["valor"].sum()
    _saldo_caixa_calc = round(_caixa_ant + _caixa_ent - _caixa_sai, 2)
    _caixa_origem = f"calculado: {fmt_br(_caixa_ant)} (ant.) + {fmt_br(_caixa_ent)} − {fmt_br(_caixa_sai)}"
else:
    _saldo_caixa_calc = float(db.carregar_saldos(mes, ano).get("saldo_caixa") or 0.0)
    _caixa_origem = "valor salvo anteriormente"

# Saldo aplicação, rendimento e resgate — do PDF de fundos
if fundos_dat and fundos_dat.get("saldo_bruto"):
    _saldo_aplic_calc   = fundos_dat["saldo_bruto"]
    _rendimento_calc    = fundos_dat["rendimento"]
    _resgate_calc       = fundos_dat["resgates"]
    _aplic_origem       = "extraído do PDF do Extrato de Fundos CEF"
else:
    _saldos_atual = db.carregar_saldos(mes, ano)
    _saldo_aplic_calc = float(_saldos_atual.get("saldo_aplicacao") or 0.0)
    _rendimento_calc  = float(_saldos_atual.get("rendimento_aplicacao") or 0.0)
    _resgate_calc     = float(_saldos_atual.get("resgate_aplicacao") or 0.0)
    _aplic_origem     = "valor salvo anteriormente"

c1, c2, c3 = st.columns(3)
with c1:
    st.caption(f"🏦 {_banco_origem}")
    saldo_banco = st.number_input(
        "Saldo Banco (R$)", value=_saldo_banco_calc,
        format="%.2f", step=100.0, key="inp_banco",
    )
with c2:
    st.caption(f"📈 {_aplic_origem}")
    saldo_aplicacao = st.number_input(
        "Saldo Aplicação (R$)", value=_saldo_aplic_calc,
        format="%.2f", step=100.0, key="inp_aplic",
    )
with c3:
    st.caption(f"💵 {_caixa_origem}")
    saldo_caixa = st.number_input(
        "Saldo Caixa — dinheiro físico (R$)", value=_saldo_caixa_calc,
        format="%.2f", step=10.0, key="inp_caixa",
    )

st.caption("Rendimentos e resgates do fundo de investimento — conforme Extrato de Fundos")
c4, c5 = st.columns(2)
with c4:
    rendimento_aplicacao = st.number_input(
        "💹 Rendimento da Aplicação no mês (R$)", value=_rendimento_calc,
        format="%.2f", step=10.0, key="inp_rendimento",
        help="Rendimento Bruto no Mês — conforme Extrato de Fundos CEF",
    )
with c5:
    resgate_aplicacao = st.number_input(
        "↩️ Resgate da Aplicação no mês (R$)", value=_resgate_calc,
        format="%.2f", step=100.0, key="inp_resgate",
        help="Resgates realizados no mês — conforme Extrato de Fundos CEF",
    )

st.divider()

# ── Botão confirmar ───────────────────────────────────────────────────────────
_itens_import = []
if sponte_df is not None: _itens_import.append(f"{len(sponte_df)} lançamentos do Sponte")
if banco_df  is not None: _itens_import.append(f"{len(banco_df)} transações do banco")
if plano_df  is not None: _itens_import.append(f"{len(plano_df)} contas do Plano de Contas")
if caixa_df  is not None: _itens_import.append(f"{len(caixa_df)} lançamentos de caixa")
if fundos_dat:             _itens_import.append("extrato de fundos")
_itens_import.append("saldos atualizados")

if st.button(f"✅ Confirmar importação de {mes_nome}/{ano}", type="primary", use_container_width=True):
    with st.spinner("Salvando dados..."):
        try:
            if sponte_df is not None:
                db.salvar_lancamentos_sponte(mes, ano, sponte_df)
            if banco_df is not None:
                db.salvar_transacoes_banco(mes, ano, banco_df)
            if plano_df is not None:
                db.salvar_plano_contas(mes, ano, plano_df)
            if caixa_df is not None:
                db.salvar_lancamentos_caixa(mes, ano, caixa_df)
            db.salvar_saldos(
                mes, ano,
                saldo_banco, saldo_aplicacao, saldo_caixa,
                rendimento_aplicacao=rendimento_aplicacao,
                resgate_aplicacao=resgate_aplicacao,
            )
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            st.stop()

    st.success(
        f"✅ **{mes_nome}/{ano} importado com sucesso!**\n\n"
        + "\n".join(f"- {item}" for item in _itens_import)
        + "\n\nAcesse o **DFC / Resumo** para ver o resultado do mês."
    )
    st.balloons()
