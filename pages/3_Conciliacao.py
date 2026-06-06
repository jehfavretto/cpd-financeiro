"""
Página: Conciliação — estilo Conta Azul
Vincula lançamentos do Sponte com transações do extrato bancário.

Fluxo:
 1. Carrega lançamentos Sponte e extrato banco do mês selecionado.
 2. Calcula chave única para cada item (data|E/S|valor).
 3. Faz auto-match dos itens com chave idêntica nos dois sistemas.
 4. Mostra itens pendentes lado a lado; usuário seleciona pares para vincular
    ou itens individuais para ignorar (com justificativa).
 5. Vínculos manuais e ignorados são persistidos no Supabase.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from collections import Counter
import db.client as db
from core.parser import MESES_ABREV
from core.utils import fmt_br

st.title("🔍 Conciliação")
st.markdown("Vincule os lançamentos do Sponte com o extrato bancário.")

# ── Seleção de mês — persiste ao trocar de página ──────────────────────────────
_anos = [2026, 2025]
col1, col2 = st.columns([1, 3])
with col1:
    _ano_idx = _anos.index(st.session_state.get("conc_ano", _anos[0]))
    ano = st.selectbox("Ano", _anos, index=_ano_idx)
    st.session_state["conc_ano"] = ano

meses_com_dados = db.meses_com_dados(ano)
if not meses_com_dados:
    st.info("Nenhum mês importado. Use **📥 Importar Mês** para começar.")
    st.stop()

with col2:
    _mes_salvo = st.session_state.get("conc_mes")
    _mes_idx   = meses_com_dados.index(_mes_salvo) if _mes_salvo in meses_com_dados else len(meses_com_dados) - 1
    mes = st.selectbox(
        "Mês", meses_com_dados,
        format_func=lambda m: f"{MESES_ABREV[m]}/{ano}",
        index=_mes_idx,
    )
    st.session_state["conc_mes"] = mes

# ── Seleciona fonte: Banco e/ou Caixa ─────────────────────────────────────────
_fc1, _fc2, _ = st.columns([2, 2, 8])
usar_banco = _fc1.checkbox("🏦 Banco", value=st.session_state.get("conc_banco", True), key=f"cb_banco_{mes}_{ano}")
usar_caixa = _fc2.checkbox("💵 Caixa", value=st.session_state.get("conc_caixa", True), key=f"cb_caixa_{mes}_{ano}")
st.session_state["conc_banco"] = usar_banco
st.session_state["conc_caixa"] = usar_caixa

if not usar_banco and not usar_caixa:
    st.warning("Selecione pelo menos uma fonte: Banco ou Caixa.")
    st.stop()

# ── Carrega dados ──────────────────────────────────────────────────────────────
sponte_df = db.carregar_lancamentos_sponte(mes, ano)
banco_df  = db.carregar_transacoes_banco(mes, ano)

def _normalizar_data_caixa(v) -> str:
    """Converte qualquer formato de data para DD/MM/YYYY."""
    try:
        return pd.to_datetime(str(v), dayfirst=True).strftime("%d/%m/%Y")
    except Exception:
        return str(v)

def _adaptar_caixa(df_cx: pd.DataFrame) -> pd.DataFrame:
    """Adapta caixa_df para ter as mesmas colunas que banco_df."""
    df_cx = df_cx.copy()
    # Normaliza data para DD/MM/YYYY (Supabase pode devolver ISO YYYY-MM-DD)
    df_cx["data_mov"] = df_cx["data_mov"].apply(_normalizar_data_caixa)
    cat  = df_cx.get("categoria", pd.Series("", index=df_cx.index)).fillna("").str.strip()
    desc = df_cx.get("descricao", pd.Series("", index=df_cx.index)).fillna("").str.strip()
    # Histórico = categoria; Nome (origem_destino) = descrição se disponível, senão categoria
    df_cx["historico"]     = cat.where(cat != "", "Caixa")
    df_cx["origem_destino"] = desc.where(desc != "", cat)
    df_cx["valor"]    = df_cx["valor"].abs()
    df_cx["data_fmt"] = df_cx["data_mov"]
    df_cx["nr_doc"]   = ""
    df_cx["chave"]    = df_cx.apply(
        lambda r: (
            f"{str(r['data_mov'])[:5]}|{r['deb_cred']}|{float(r['valor']):.2f}"
            f"|{_norm_nome(str(r.get('descricao', '') or '').strip())}"
        ).replace(".", ","),
        axis=1
    )
    return df_cx

# Carrega caixa sempre (para auto-match não quebrar ao filtrar fonte)
_caixa_raw = db.carregar_lancamentos_caixa(mes, ano)
_caixa_adaptado = _adaptar_caixa(_caixa_raw) if not _caixa_raw.empty else pd.DataFrame()

# banco_df_full: todos os dados disponíveis (usado em auto-match e conciliados)
_partes_full = [p for p in [banco_df if not banco_df.empty else None,
                              _caixa_adaptado if not _caixa_adaptado.empty else None]
                if p is not None]
banco_df_full = pd.concat(_partes_full, ignore_index=True) if _partes_full else pd.DataFrame()

# banco_df: apenas a fonte selecionada (usado nos pendentes)
if usar_caixa and not usar_banco:
    if _caixa_adaptado.empty:
        st.info("Nenhum lançamento de caixa importado para este mês. Use **📥 Importar Mês** para carregar a planilha de caixa.")
        st.stop()
    banco_df = _caixa_adaptado
elif usar_banco and usar_caixa and not _caixa_adaptado.empty:
    banco_df = pd.concat([banco_df, _caixa_adaptado], ignore_index=True)
# se só banco: banco_df já está correto

# Título dinâmico do extrato
_titulo_extrato = (
    "🏦💵 Banco + Caixa" if (usar_banco and usar_caixa)
    else "💵 Extrato Caixa" if usar_caixa
    else "🏦 Extrato Banco"
)

if sponte_df.empty or banco_df_full.empty:
    st.warning("Dados de lançamentos não encontrados para este mês.")
    st.stop()

# ── Tabela alunos → mapa aluno → responsável(is) ──────────────────────────────
import unicodedata as _ucd

def _norm_nome(s: str) -> str:
    """Normaliza nome para comparação: minúsculas sem acentos."""
    s = _ucd.normalize("NFD", str(s).lower().strip())
    return "".join(c for c in s if _ucd.category(c) != "Mn")

try:
    _alunos_df = db.carregar_alunos(ano)
except Exception:
    _alunos_df = pd.DataFrame(columns=["nome_aluno", "nome_responsavel"])

# {nome_aluno_normalizado: "Resp1 / Resp2"}
_aluno_resp_map: dict[str, str] = {}
# {nome_resp_normalizado: "Aluno1 / Aluno2"}
_resp_aluno_map: dict[str, str] = {}
if not _alunos_df.empty:
    for aluno, grp in _alunos_df.groupby("nome_aluno")["nome_responsavel"]:
        resps = [r for r in grp.tolist() if str(r).strip()]
        if resps:
            _aluno_resp_map[_norm_nome(aluno)] = " / ".join(resps)
    for resp, grp in _alunos_df.groupby("nome_responsavel")["nome_aluno"]:
        alunos = [a for a in grp.tolist() if str(a).strip()]
        if alunos:
            _resp_aluno_map[_norm_nome(resp)] = " / ".join(alunos)

def _responsavel_do_aluno(nome_aluno: str) -> str:
    return _aluno_resp_map.get(_norm_nome(nome_aluno), "")

def _aluno_do_responsavel(nome_resp: str) -> str:
    return _resp_aluno_map.get(_norm_nome(nome_resp), "")


# ── Funções auxiliares ─────────────────────────────────────────────────────────

def _data_banco_fmt(data_mov: str) -> str:
    """Data já vem normalizada como DD/MM/YYYY do parser/load."""
    return str(data_mov).strip()


def _md_val(v) -> str:
    """Formata valor em BR e escapa o $ para não ser interpretado como LaTeX."""
    return fmt_br(abs(float(v))).replace("$", r"\$")


def _html_val(v) -> str:
    """Formata valor em BR e escapa o $ para contexto HTML."""
    return fmt_br(abs(float(v))).replace("$", "&#36;")


def make_key_sponte(row) -> str:
    d = row["data"]
    dia_mes = f"{d.day:02d}/{d.month:02d}"
    aluno = str(row.get("origem_destino", "")).strip()
    resp_str = _aluno_resp_map.get(_norm_nome(aluno), "")
    # usa o primeiro responsável; se não cadastrado, usa o próprio nome do aluno
    resp_norm = _norm_nome(resp_str.split(" / ")[0]) if resp_str else _norm_nome(aluno)
    return f"{dia_mes}|{row['es']}|{float(row['valor']):.2f}|{resp_norm}".replace(".", ",")


def make_key_banco(row) -> str:
    dia_mes = str(row["data_mov"])[:5]        # "DD/MM/YYYY" → "DD/MM"
    nome = str(row.get("origem_destino", "") or "").strip()
    nome_norm = _norm_nome(nome) if nome else ""
    return f"{dia_mes}|{row['deb_cred']}|{float(row['valor']):.2f}|{nome_norm}".replace(".", ",")


# ── Prepara DataFrames ─────────────────────────────────────────────────────────
sponte_df    = sponte_df.copy()
banco_df     = banco_df.copy()
banco_df_full = banco_df_full.copy()
sponte_df["chave"]         = sponte_df.apply(make_key_sponte, axis=1)
banco_df["chave"]          = banco_df.apply(make_key_banco, axis=1)
banco_df["data_fmt"]       = banco_df["data_mov"].apply(_data_banco_fmt)
banco_df_full["chave"]     = banco_df_full.apply(make_key_banco, axis=1)
banco_df_full["data_fmt"]  = banco_df_full["data_mov"].apply(_data_banco_fmt)

# ── Carrega conciliações já salvas ─────────────────────────────────────────────
try:
    conciliacoes = db.carregar_conciliacoes(mes, ano)
except Exception as _e:
    st.error(f"DEBUG — erro em carregar_conciliacoes: {type(_e).__name__}: {_e}")
    st.stop()
if conciliacoes:
    conc_df = pd.DataFrame(conciliacoes)
else:
    conc_df = pd.DataFrame(columns=["id", "tipo", "sponte_chave", "banco_chave", "justificativa"])

# Registros "desvincular" não entram em usadas — itens voltam para pendentes
_desv          = conc_df[conc_df["tipo"] == "desvincular"]
_conc_sem_desv = conc_df[conc_df["tipo"] != "desvincular"]

chaves_sp_desvincular = set(_desv["sponte_chave"].dropna()) if not _desv.empty else set()

# ── Monta contadores de uso manual ────────────────────────────────────────────
# banco_chave pode conter múltiplas chaves separadas por §§ (formato 1→N)
# sp_manual_cnt[X] = nº de operações de linkage que consumiram o Sponte X (1 por vinculação)
_cnt_sp = Counter(sponte_df["chave"])
_cnt_bk = Counter(banco_df_full["chave"])

sp_manual_cnt: Counter = Counter()
bk_manual_cnt: Counter = Counter()   # conta cada banco_chave individual

for _, _row in _conc_sem_desv.iterrows():
    _sp_ch = _row.get("sponte_chave")
    _bk_ch = _row.get("banco_chave")
    if pd.notna(_sp_ch):
        sp_manual_cnt[_sp_ch] += 1
    if pd.notna(_bk_ch):
        for _ch in str(_bk_ch).split("§§"):
            _ch = _ch.strip()
            if _ch:
                bk_manual_cnt[_ch] += 1

chaves_bk_usadas = set(bk_manual_cnt.keys())

# ── Auto-match: disponível = total_no_df − uso_manual ─────────────────────────
# Evita que um 1→N bloqueie o auto-match de outros Sponte com a mesma chave
_sp_available = {
    ch: max(0, _cnt_sp[ch] - sp_manual_cnt.get(ch, 0)) for ch in _cnt_sp
}
_bk_available = {
    ch: max(0, _cnt_bk[ch] - bk_manual_cnt.get(ch, 0)) for ch in _cnt_bk
}

_raw_auto = {
    ch for ch in set(_sp_available) & set(_bk_available)
    if _sp_available[ch] > 0 and _bk_available[ch] > 0
    and ch not in chaves_sp_desvincular
}
chaves_auto_counts = {ch: min(_sp_available[ch], _bk_available[ch]) for ch in _raw_auto}

# Índices já consumidos pelo linkage manual
bk_manually_used_idx: set = set()
for _ch, _cnt in bk_manual_cnt.items():
    bk_manually_used_idx.update(banco_df[banco_df["chave"] == _ch].index[:_cnt].tolist())

# sp_manually_used_idx: prefere consumir Sponte que NÃO conseguem auto-matchear,
# preservando os que podem casar com banco disponível
def _sp_pode_automatch(sp_origem: str, bk_rows_df) -> bool:
    """Retorna True se este Sponte pode casar com algum banco disponível."""
    if bk_rows_df.empty:
        return False
    sp_norm = _norm_nome(sp_origem)
    resp_str = _aluno_resp_map.get(sp_norm, "")
    resps = {_norm_nome(r) for r in resp_str.split(" / ") if r.strip()} if resp_str else set()
    for _, _bk_r in bk_rows_df.iterrows():
        bk_orig = str(_bk_r.get("origem_destino", "")).strip()
        if not bk_orig or not sp_origem:
            return True   # sem nome = não dá para bloquear
        if not resps:
            return True   # sem responsáveis cadastrados = não dá para bloquear
        bk_norm = _norm_nome(bk_orig)
        if bk_norm == sp_norm or bk_norm in resps:
            return True
    return False

sp_manually_used_idx: set = set()
for _ch, _cnt in sp_manual_cnt.items():
    _sp_rows = sponte_df[sponte_df["chave"] == _ch]
    if len(_sp_rows) <= _cnt:
        sp_manually_used_idx.update(_sp_rows.index.tolist())
        continue
    _bk_disp = banco_df_full[
        (banco_df_full["chave"] == _ch) & (~banco_df_full.index.isin(bk_manually_used_idx))
    ]
    _incompat, _compat = [], []
    for _idx, _sp_r in _sp_rows.iterrows():
        sp_orig = str(_sp_r.get("origem_destino", "")).strip()
        if _sp_pode_automatch(sp_orig, _bk_disp):
            _compat.append(_idx)
        else:
            _incompat.append(_idx)
    sp_manually_used_idx.update((_incompat + _compat)[:_cnt])

# ── Helpers de verificação de nome para auto-match ────────────────────────────
def _resps_do_aluno_set(nome_aluno: str) -> set:
    """Retorna set de responsáveis normalizados do aluno (vazio se não cadastrado)."""
    resp_str = _aluno_resp_map.get(_norm_nome(nome_aluno), "")
    if not resp_str:
        return set()
    return {_norm_nome(r) for r in resp_str.split(" / ") if r.strip()}

def _nome_compativel(sp_row, bk_row) -> bool:
    """
    Retorna True se o par sp+bk é compatível por nome, ou se não dá para verificar.
    Incompatível somente quando há dados suficientes e os nomes claramente não batem.
    Aceita:
      - banco tem o nome do responsável do aluno Sponte
      - banco tem o próprio nome do aluno Sponte
    """
    bk_nome = str(bk_row.get("origem_destino", "")).strip()
    if not bk_nome:
        return True  # banco sem nome: não dá para verificar
    sp_aluno = str(sp_row.get("origem_destino", "")).strip()
    if not sp_aluno:
        return True  # sponte sem aluno: não dá para verificar

    bk_norm = _norm_nome(bk_nome)

    # Caso 1: banco tem o próprio nome do aluno
    if bk_norm == _norm_nome(sp_aluno):
        return True

    resps = _resps_do_aluno_set(sp_aluno)
    if not resps:
        return True  # aluno sem responsáveis cadastrados: não dá para verificar

    # Caso 2: banco tem o nome de um responsável do aluno
    return bk_norm in resps

# Índices do auto-match com verificação de nome
_sp_idx_auto: set = set()
_bk_idx_auto: set = set()
for _chave, _n in chaves_auto_counts.items():
    _sp_cands = sponte_df[
        (sponte_df["chave"] == _chave) & (~sponte_df.index.isin(sp_manually_used_idx))
    ].copy()
    _bk_cands = banco_df_full[
        (banco_df_full["chave"] == _chave) & (~banco_df_full.index.isin(bk_manually_used_idx))
    ].copy()

    if _sp_cands.empty or _bk_cands.empty:
        continue

    # Tenta fazer pares verificando compatibilidade de nome
    _sp_usados: set = set()
    _bk_usados: set = set()
    _pares_ok: list = []
    _pares_sem_verif: list = []

    for _si, _sp_r in _sp_cands.iterrows():
        for _bi, _bk_r in _bk_cands.iterrows():
            if _bi in _bk_usados:
                continue
            if _nome_compativel(_sp_r, _bk_r):
                _pares_ok.append((_si, _bi))
                _bk_usados.add(_bi)
                _sp_usados.add(_si)
                break

    # Pares confirmados (até _n)
    for _si, _bi in _pares_ok[:_n]:
        _sp_idx_auto.add(_si)
        _bk_idx_auto.add(_bi)

# ── Separa pendentes ───────────────────────────────────────────────────────────
mask_sp_ok = sponte_df.index.isin(_sp_idx_auto) | sponte_df.index.isin(sp_manually_used_idx)
# pendentes do banco: filtra só pela fonte selecionada (banco_df já tem só a fonte do filtro)
_bk_full_ok = banco_df_full.index.isin(_bk_idx_auto) | banco_df_full.index.isin(bk_manually_used_idx)
_bk_full_pendente = banco_df_full[~_bk_full_ok]
# mantém só linhas da fonte selecionada (banco_df) que também estão pendentes no full
mask_bk_ok = banco_df.index.isin(_bk_full_pendente.index)
sponte_pendente = sponte_df[~mask_sp_ok].reset_index(drop=True)
banco_pendente  = banco_df[mask_bk_ok].reset_index(drop=True)


# ── Barra de progresso ─────────────────────────────────────────────────────────
total_sp   = len(sponte_df)
total_bk   = len(banco_df_full)
total      = total_sp + total_bk
_bk_full_pend_count = len(banco_df_full[~(banco_df_full.index.isin(_bk_idx_auto) | banco_df_full.index.isin(bk_manually_used_idx))])
pendente   = len(sponte_pendente) + _bk_full_pend_count
conciliado = total - pendente
pct        = conciliado / total if total else 0.0

st.markdown("### Progresso")
st.progress(
    pct,
    text=(
        f"**{conciliado} de {total}** itens conciliados ({pct:.0%}) — "
        f"{len(sponte_pendente)} Sponte + {_bk_full_pend_count} Banco ainda pendentes"
    ),
)
st.divider()

# ── Seção: Conciliados ─────────────────────────────────────────────────────────
# n_auto = pares realmente matchados (índices em _sp_idx_auto/_bk_idx_auto)
n_auto   = len(_sp_idx_auto)
n_manual = int((conc_df["tipo"] == "manual").sum()) if not conc_df.empty else 0
n_ign    = int(conc_df["tipo"].str.startswith("ignorado", na=False).sum()) if not conc_df.empty else 0

# ── Abas: Pendentes / Conciliados ─────────────────────────────────────────────
aba_pend, aba_conc = st.tabs([
    f"⏳ Pendentes ({len(sponte_pendente)} Sponte · {len(banco_pendente)} Banco)",
    f"✅ Conciliados ({n_auto} automáticos · {n_manual} manuais · {n_ign} ignorados)",
])

# ══════════════════════════════════════════════════════════════════════════════
# ABA: PENDENTES
# ══════════════════════════════════════════════════════════════════════════════
with aba_pend:

    if sponte_pendente.empty and banco_pendente.empty:
        st.success("🎉 **Conciliação completa!** Todos os lançamentos foram conciliados.")
    else:
        st.caption(
            "Selecione **uma ou mais linhas** do Sponte e **uma linha** do Banco para vincular, "
            "ou apenas **um lado** para ignorar com justificativa."
        )

        # ── Filtros ───────────────────────────────────────────────────────────
        if "flt_cnt" not in st.session_state:
            st.session_state["flt_cnt"] = 0
        _fc = st.session_state["flt_cnt"]

        fb1, fb2, fb3 = st.columns([5, 4, 1])
        busca = fb1.text_input(
            "Pesquisar", placeholder="🔍  categoria, origem/destino, histórico…",
            key=f"busca_{mes}_{ano}_{_fc}",
        )
        filtro_es = fb2.radio(
            "Tipo:", ["Todos", "Entradas (E)", "Saídas (S)"],
            horizontal=True, key=f"filtro_es_{mes}_{ano}_{_fc}",
        )
        fb3.write(""); fb3.write("")
        if fb3.button("✕", key=f"limpar_{mes}_{ano}", help="Limpar todos os filtros"):
            st.session_state["flt_cnt"] += 1
            st.rerun()

        with st.expander("⚙️ Mais filtros"):
            mf1, mf2, mf3 = st.columns([2, 2, 4])
            val_min = mf1.number_input(
                "Valor mínimo (R$)", min_value=0.0, value=0.0,
                step=50.0, format="%.2f", key=f"vmin_{mes}_{ano}_{_fc}",
            )
            val_max = mf2.number_input(
                "Valor máximo (R$)", min_value=0.0, value=0.0,
                step=50.0, format="%.2f", key=f"vmax_{mes}_{ano}_{_fc}",
                help="0 = sem limite",
            )
            cats = sorted(sponte_pendente["categoria"].dropna().unique().tolist())
            cat_sel = mf3.multiselect(
                "Categoria (Sponte)", cats, key=f"cat_{mes}_{ano}_{_fc}",
                placeholder="Selecione categorias…",
            )

        # ── Aplica filtros ────────────────────────────────────────────────────
        sp_filtrado = sponte_pendente.copy()
        bk_filtrado = banco_pendente.copy()

        if filtro_es == "Entradas (E)":
            sp_filtrado = sp_filtrado[sp_filtrado["es"] == "E"]
            bk_filtrado = bk_filtrado[bk_filtrado["deb_cred"] == "E"]
        elif filtro_es == "Saídas (S)":
            sp_filtrado = sp_filtrado[sp_filtrado["es"] == "S"]
            bk_filtrado = bk_filtrado[bk_filtrado["deb_cred"] == "S"]

        if busca.strip():
            q = busca.strip().lower()
            # Sponte: pesquisa em categoria, aluno e responsável
            _sp_resp_filt = sp_filtrado["origem_destino"].apply(_responsavel_do_aluno)
            sp_filtrado = sp_filtrado[
                sp_filtrado["categoria"].str.lower().str.contains(q, na=False) |
                sp_filtrado["origem_destino"].str.lower().str.contains(q, na=False) |
                _sp_resp_filt.str.lower().str.contains(q, na=False)
            ]
            # Banco: pesquisa em histórico e origem/destino (nome do responsável)
            bk_od = bk_filtrado["origem_destino"] if "origem_destino" in bk_filtrado.columns else pd.Series("", index=bk_filtrado.index)
            bk_filtrado = bk_filtrado[
                bk_filtrado["historico"].str.lower().str.contains(q, na=False) |
                bk_od.str.lower().str.contains(q, na=False)
            ]

        if val_min > 0:
            sp_filtrado = sp_filtrado[sp_filtrado["valor"].abs() >= val_min]
            bk_filtrado = bk_filtrado[bk_filtrado["valor"].abs() >= val_min]
        if val_max > 0:
            sp_filtrado = sp_filtrado[sp_filtrado["valor"].abs() <= val_max]
            bk_filtrado = bk_filtrado[bk_filtrado["valor"].abs() <= val_max]

        if cat_sel:
            sp_filtrado = sp_filtrado[sp_filtrado["categoria"].isin(cat_sel)]

        # Contador de ações — incrementar após cada ação reseta as seleções
        if "conc_cnt" not in st.session_state:
            st.session_state["conc_cnt"] = 0
        cnt    = st.session_state["conc_cnt"]
        sp_key = f"dfsp_{mes}_{ano}_{cnt}"
        bk_key = f"dfbk_{mes}_{ano}_{cnt}"

        col_sp, col_mid, col_bk = st.columns([5, 2, 5])

        _val_cfg  = st.column_config.NumberColumn("Valor",          format="R$ %,.2f", width=110)
        _es_cfg   = st.column_config.TextColumn("E/S",             width=45)
        _dat_cfg  = st.column_config.TextColumn("Data",            width=55)
        _cat_cfg  = st.column_config.TextColumn("Categoria",    width=130)
        _alu_cfg  = st.column_config.TextColumn("Aluno",        width=180)
        _resp_cfg = st.column_config.TextColumn("Responsável",  width=180)
        _his_cfg  = st.column_config.TextColumn("Histórico",    width=130)

        _resp_series = sp_filtrado["origem_destino"].apply(_responsavel_do_aluno)
        sp_show_full = pd.DataFrame({
            "Data":        pd.to_datetime(sp_filtrado["data"]).dt.strftime("%d/%m"),
            "E/S":         sp_filtrado["es"],
            "Valor":       sp_filtrado["valor"].abs(),
            "Categoria":   sp_filtrado["categoria"],
            "Aluno":       sp_filtrado["origem_destino"],
            "Responsável": _resp_series,
        })

        _tem_orig = "origem_destino" in bk_filtrado.columns
        _bk_nome = (
            bk_filtrado["origem_destino"]
            .where(bk_filtrado["origem_destino"].fillna("").str.strip() != "",
                   bk_filtrado["historico"])
            if _tem_orig else bk_filtrado["historico"]
        )
        def _bk_aluno_resp(nome: str):
            """Dado um nome do banco, retorna (aluno, responsável).
            Se o nome é responsável → (aluno lookup, nome).
            Se o nome é aluno      → (nome, responsável lookup).
            Se nenhum dos dois     → ('', nome).
            """
            if not nome or nome.lower() == "nan":
                return "", ""
            aluno = _aluno_do_responsavel(nome)
            if aluno:
                return aluno, nome          # nome é responsável
            resp = _responsavel_do_aluno(nome)
            if resp:
                return nome, resp           # nome é aluno
            return "", nome                 # desconhecido → só responsável

        _bk_aluno_col  = _bk_nome.apply(lambda n: _bk_aluno_resp(n)[0])
        _bk_resp_col   = _bk_nome.apply(lambda n: _bk_aluno_resp(n)[1])

        bk_show_full = pd.DataFrame({
            "Data":        bk_filtrado["data_fmt"].str[:5],
            "E/S":         bk_filtrado["deb_cred"],
            "Valor":       bk_filtrado["valor"].abs(),
            "Aluno":       _bk_aluno_col,
            "Responsável": _bk_resp_col,
            "Histórico":   bk_filtrado["historico"],
        })

        # ── Defaults de configuração de tabela ───────────────────────────────
        _SP_COLS_DEF = ["Data", "E/S", "Valor", "Categoria", "Aluno", "Responsável"]
        _BK_COLS_DEF = ["Data", "E/S", "Valor", "Aluno", "Responsável", "Histórico"]
        _SP_SORT_DEF = "Data"
        _BK_SORT_DEF = "Data"

        _sk = f"{mes}_{ano}"   # chave base para session_state

        if f"sp_cols_{_sk}" not in st.session_state:
            st.session_state[f"sp_cols_{_sk}"] = _SP_COLS_DEF
        if f"bk_cols_{_sk}" not in st.session_state:
            st.session_state[f"bk_cols_{_sk}"] = _BK_COLS_DEF
        if f"sp_sort_{_sk}" not in st.session_state:
            st.session_state[f"sp_sort_{_sk}"] = _SP_SORT_DEF
        if f"sp_asc_{_sk}" not in st.session_state:
            st.session_state[f"sp_asc_{_sk}"] = True
        if f"bk_sort_{_sk}" not in st.session_state:
            st.session_state[f"bk_sort_{_sk}"] = _BK_SORT_DEF
        if f"bk_asc_{_sk}" not in st.session_state:
            st.session_state[f"bk_asc_{_sk}"] = True

        class _EmptySel:
            class selection:
                rows = []

        def _msg_vazia(tudo_conciliado: bool) -> str:
            if tudo_conciliado:
                return (
                    "<div style='height:400px;display:flex;flex-direction:column;"
                    "align-items:center;justify-content:center;gap:8px;"
                    "color:#1a7f37;font-weight:600;font-size:1rem;"
                    "background:#f0fff4;border-radius:8px;"
                    "border:1px solid #c3e6cb;'>"
                    "<span style='font-size:2rem'>✅</span>"
                    "Tudo conciliado!"
                    "</div>"
                )
            else:
                return (
                    "<div style='height:400px;display:flex;flex-direction:column;"
                    "align-items:center;justify-content:center;gap:8px;"
                    "color:#6c757d;font-weight:500;font-size:0.95rem;"
                    "background:#f8f9fa;border-radius:8px;"
                    "border:1px solid #dee2e6;'>"
                    "<span style='font-size:2rem'>🔍</span>"
                    "Nenhum lançamento neste filtro"
                    "</div>"
                )

        with col_sp:
            st.markdown("**📋 FluxoCaixa Sponte**")
            st.markdown('<div class="cpd-sort">', unsafe_allow_html=True)
            _sc1, _sc2 = st.columns([3, 2])
            _sp_sort = _sc1.selectbox(
                "Ordenar por", ["Data","Valor","Categoria","Aluno","Responsável"],
                index=["Data","Valor","Categoria","Aluno","Responsável"].index(
                    st.session_state[f"sp_sort_{_sk}"] if st.session_state[f"sp_sort_{_sk}"] in ["Data","Valor","Categoria","Aluno","Responsável"] else "Data"
                ),
                key=f"sp_sort_sel_{_sk}", label_visibility="collapsed",
            )
            _sp_asc = _sc2.radio(
                "Ordem", ["Crescente","Decrescente"],
                index=0 if st.session_state[f"sp_asc_{_sk}"] else 1,
                horizontal=True, key=f"sp_ord_{_sk}", label_visibility="collapsed",
            )
            st.session_state[f"sp_sort_{_sk}"] = _sp_sort
            st.session_state[f"sp_asc_{_sk}"]  = (_sp_asc == "Crescente")

            with st.popover("⚙️ Colunas visíveis", use_container_width=True):
                _sp_cols_vis = st.multiselect(
                    "Colunas Sponte", _SP_COLS_DEF,
                    default=st.session_state[f"sp_cols_{_sk}"],
                    key=f"sp_cols_sel_{_sk}", label_visibility="collapsed",
                ) or _SP_COLS_DEF
            st.session_state[f"sp_cols_{_sk}"] = _sp_cols_vis
            st.markdown('</div>', unsafe_allow_html=True)

            # Aplica ordenação — guarda mapeamento pos→índice original
            _sp_sort_col = _sp_sort if _sp_sort in sp_show_full.columns else "Data"
            _sp_sorted_idx = sp_show_full.sort_values(
                _sp_sort_col, ascending=st.session_state[f"sp_asc_{_sk}"]
            ).index.tolist()
            sp_show = sp_show_full.loc[_sp_sorted_idx, _sp_cols_vis].reset_index(drop=True)

            if sp_show.empty:
                sel_sp = _EmptySel()
                st.markdown(_msg_vazia(sponte_pendente.empty), unsafe_allow_html=True)
            else:
                _sp_cfg = {c: cfg for c, cfg in {
                    "Data": _dat_cfg, "E/S": _es_cfg, "Valor": _val_cfg,
                    "Categoria": _cat_cfg, "Aluno": _alu_cfg, "Responsável": _resp_cfg,
                }.items() if c in _sp_cols_vis}
                sel_sp = st.dataframe(
                    sp_show,
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                    column_config=_sp_cfg,
                    selection_mode="multi-row",
                    on_select="rerun",
                    key=sp_key,
                )

        with col_bk:
            st.markdown(f"**{_titulo_extrato}**")
            st.markdown('<div class="cpd-sort">', unsafe_allow_html=True)
            _bc1, _bc2 = st.columns([3, 2])
            _bk_sort = _bc1.selectbox(
                "Ordenar por", ["Data","Valor","Nome","Histórico"],
                index=["Data","Valor","Nome","Histórico"].index(
                    st.session_state[f"bk_sort_{_sk}"]
                ),
                key=f"bk_sort_sel_{_sk}", label_visibility="collapsed",
            )
            _bk_asc = _bc2.radio(
                "Ordem", ["Crescente","Decrescente"],
                index=0 if st.session_state[f"bk_asc_{_sk}"] else 1,
                horizontal=True, key=f"bk_ord_{_sk}", label_visibility="collapsed",
            )
            st.session_state[f"bk_sort_{_sk}"] = _bk_sort
            st.session_state[f"bk_asc_{_sk}"]  = (_bk_asc == "Crescente")

            with st.popover("⚙️ Colunas visíveis", use_container_width=True):
                _bk_cols_vis = st.multiselect(
                    "Colunas Banco", _BK_COLS_DEF,
                    default=st.session_state[f"bk_cols_{_sk}"],
                    key=f"bk_cols_sel_{_sk}", label_visibility="collapsed",
                ) or _BK_COLS_DEF
            st.session_state[f"bk_cols_{_sk}"] = _bk_cols_vis
            st.markdown('</div>', unsafe_allow_html=True)

            _bk_sort_col = _bk_sort if _bk_sort in bk_show_full.columns else "Data"
            _bk_sorted_idx = bk_show_full.sort_values(
                _bk_sort_col, ascending=st.session_state[f"bk_asc_{_sk}"]
            ).index.tolist()
            bk_show = bk_show_full.loc[_bk_sorted_idx, _bk_cols_vis].reset_index(drop=True)

            if bk_show.empty:
                sel_bk = _EmptySel()
                st.markdown(_msg_vazia(banco_pendente.empty), unsafe_allow_html=True)
            else:
                _bk_cfg = {c: cfg for c, cfg in {
                    "Data": _dat_cfg, "E/S": _es_cfg, "Valor": _val_cfg,
                    "Aluno": _alu_cfg, "Responsável": _resp_cfg, "Histórico": _his_cfg,
                }.items() if c in _bk_cols_vis}
                sel_bk = st.dataframe(
                    bk_show,
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                    column_config=_bk_cfg,
                    selection_mode="multi-row",
                    on_select="rerun",
                    key=bk_key,
                )

        # Mapeia posições selecionadas → índices originais (respeitando a ordenação)
        _sp_raw_rows = sel_sp.selection.rows if hasattr(sel_sp, "selection") else []
        _bk_raw_rows = sel_bk.selection.rows if hasattr(sel_bk, "selection") else []
        sp_sel_rows = [_sp_sorted_idx[i] for i in _sp_raw_rows if i < len(_sp_sorted_idx)]
        bk_sel_rows = [_bk_sorted_idx[i] for i in _bk_raw_rows if i < len(_bk_sorted_idx)]
        n_sp = len(sp_sel_rows)
        n_bk = len(bk_sel_rows)

        with col_mid:
            # empurra para baixo para alinhar com as tabelas
            st.markdown("""
            <style>
            [data-testid="stSelectbox"] div[data-baseweb="select"] *,
            [data-testid="stRadio"] label p,
            [data-testid="stExpander"] summary p { font-size: 0.8rem !important; }
            </style>
            <div style="height:188px"></div>
            """, unsafe_allow_html=True)
            st.markdown("<p style='text-align:center;font-weight:600;color:#555;margin-bottom:4px'>Ações</p><hr style='margin:0 0 8px 0'>", unsafe_allow_html=True)

            if n_sp > 0 and n_bk > 0:
                # ── N Sponte → 1 Banco  ou  1 Sponte → N Banco ────────────────
                sp_selecionados = [sp_filtrado.loc[i] for i in sp_sel_rows]
                bk_selecionados = [bk_filtrado.loc[i] for i in bk_sel_rows]
                soma_sp = sum(abs(r["valor"]) for r in sp_selecionados)
                soma_bk = sum(abs(float(r["valor"])) for r in bk_selecionados)
                diff = abs(soma_sp - soma_bk)

                if n_sp > 1 and n_bk > 1:
                    st.warning("Selecione **1 Banco** para vários Sponte, ou **1 Sponte** para vários Banco.")
                else:
                    for r in sp_selecionados:
                        st.caption(f"🔵 {str(r['categoria'])[:22]}  \n**{_md_val(r['valor'])}**")
                    if n_sp > 1:
                        st.markdown(
                            f"<span style='font-size:0.9rem;color:#888;font-weight:700'>"
                            f"Total {_html_val(soma_sp)}</span>",
                            unsafe_allow_html=True,
                        )
                    for r in bk_selecionados:
                        st.caption(f"🏦 {str(r['historico'])[:22]}  \n**{_md_val(float(r['valor']))}**")
                    if n_bk > 1:
                        st.markdown(
                            f"<span style='font-size:0.9rem;color:#888;font-weight:700'>"
                            f"Total {_html_val(soma_bk)}</span>",
                            unsafe_allow_html=True,
                        )

                    _MOTIVOS_DIF = [
                        "Pagamento agrupado (vários alunos)",
                        "Desconto concedido",
                        "Juros / multa por atraso",
                        "Pagamento parcial",
                        "Complemento de pagamento anterior",
                        "Erro de lançamento no Sponte",
                        "Outro",
                    ]
                    _justificativa = None
                    if diff > 0.02:
                        st.warning(f"⚠️ Dif: {_md_val(diff)}")
                        _justificativa = st.selectbox(
                            "Motivo:", _MOTIVOS_DIF,
                            key=f"motivo_dif_{cnt}",
                        )

                    if n_sp > 1:
                        lbl = f"🔗 Vincular {n_sp}→1"
                    elif n_bk > 1:
                        lbl = f"🔗 Vincular 1→{n_bk}"
                    else:
                        lbl = "🔗 Vincular"
                    if st.button(lbl, type="primary", use_container_width=True):
                        if n_bk == 1:
                            bk_r = bk_selecionados[0]
                            for r in sp_selecionados:
                                db.salvar_conciliacao(mes, ano, "manual",
                                                      sponte_chave=r["chave"],
                                                      banco_chave=bk_r["chave"],
                                                      justificativa=_justificativa)
                        else:
                            sp_r = sp_selecionados[0]
                            bk_chaves_unidas = "§§".join(r["chave"] for r in bk_selecionados)
                            db.salvar_conciliacao(mes, ano, "manual",
                                                  sponte_chave=sp_r["chave"],
                                                  banco_chave=bk_chaves_unidas,
                                                  justificativa=_justificativa)
                        st.session_state["conc_cnt"] += 1
                        st.rerun()

            elif n_sp > 0:
                # ── Só Sponte selecionado ─────────────────────────────────────
                sp_selecionados = [sp_filtrado.loc[i] for i in sp_sel_rows]
                soma_sp = sum(abs(r["valor"]) for r in sp_selecionados)

                for r in sp_selecionados:
                    st.caption(f"🔵 {str(r['categoria'])[:22]}  \n**{_md_val(r['valor'])}**")
                if n_sp > 1:
                    st.markdown(
                        f"<span style='font-size:0.9rem;color:#888;font-weight:700'>"
                        f"Total {_html_val(soma_sp)}</span>",
                        unsafe_allow_html=True,
                    )

                if n_sp == 1:
                    sp_r = sp_filtrado.loc[sp_sel_rows[0]]
                    st.caption("*Selecione Banco(s) para vincular, ou ignore:*")
                    # Botões de justificativa rápida
                    _MOTIVOS_RAPIDOS = ["Desconto em folha", "Pago em caixa físico", "Estorno/Cancelamento"]
                    for _mot in _MOTIVOS_RAPIDOS:
                        if st.button(_mot, key=f"ign_rapido_{_mot}_{cnt}", use_container_width=True):
                            db.salvar_conciliacao(mes, ano, "ignorado_sponte",
                                                  sponte_chave=sp_r["chave"],
                                                  justificativa=_mot)
                            st.session_state["conc_cnt"] += 1
                            st.rerun()
                    with st.form(key=f"form_isp_{cnt}"):
                        just = st.text_input("Outro motivo:", placeholder="ex: saída em caixa físico")
                        if st.form_submit_button("🙈 Ignorar Sponte", use_container_width=True):
                            db.salvar_conciliacao(mes, ano, "ignorado_sponte",
                                                  sponte_chave=sp_r["chave"],
                                                  justificativa=just or None)
                            st.session_state["conc_cnt"] += 1
                            st.rerun()
                else:
                    st.caption("*Selecione 1 linha do Banco para vincular.*")

            elif n_bk > 0:
                # ── Só Banco selecionado ──────────────────────────────────────
                if n_bk == 1:
                    bk_r = bk_filtrado.loc[bk_sel_rows[0]]
                    st.caption(f"🏦 {str(bk_r['historico'])[:22]}  \n**{_md_val(float(bk_r['valor']))}**")
                    with st.form(key=f"form_ibk_{cnt}"):
                        just = st.text_input("Motivo:", placeholder="ex: tarifa bancária")
                        if st.form_submit_button("🙈 Ignorar Banco", use_container_width=True):
                            db.salvar_conciliacao(mes, ano, "ignorado_banco",
                                                  banco_chave=bk_r["chave"],
                                                  justificativa=just or None)
                            st.session_state["conc_cnt"] += 1
                            st.rerun()
                else:
                    st.caption("*Selecione também 1 Sponte para vincular.*")

            else:
                st.caption(
                    "👈 Selecione linhas do **Sponte** e do **Banco** para vincular.\n\n"
                    "Ou selecione apenas um lado para ignorar."
                )

# ══════════════════════════════════════════════════════════════════════════════
# ABA: CONCILIADOS
# ══════════════════════════════════════════════════════════════════════════════

# ── Helpers de texto simples para dataframes (sem escape markdown) ────────────
def _sp_txt(chave: str) -> str:
    r = sponte_df[sponte_df["chave"] == chave]
    if r.empty:
        return str(chave)
    row = r.iloc[0]
    nome = str(row.get("origem_destino", "")).strip()
    nome_part = f" · {nome}" if nome else ""
    return f"{pd.to_datetime(row['data']).strftime('%d/%m')} · {str(row['categoria'])}{nome_part} · {fmt_br(abs(row['valor']))}"

def _bk_txt(chave: str) -> str:
    r = banco_df_full[banco_df_full["chave"] == chave]
    if r.empty:
        return str(chave)
    row = r.iloc[0]
    nome = str(row.get("origem_destino", "")).strip()
    nome_part = f" · {nome}" if nome else ""
    return f"{row['data_fmt'][:5]} · {str(row['historico'])}{nome_part} · {fmt_br(abs(float(row['valor'])))}"

with aba_conc:
    if n_auto == 0 and n_manual == 0 and n_ign == 0:
        st.info("Nenhum item conciliado ainda.")

    # ── Pesquisa nos conciliados ──────────────────────────────────────────────
    busca_conc = st.text_input(
        "Pesquisar conciliados",
        placeholder="🔍  categoria, nome, histórico, valor…",
        key=f"busca_conc_{mes}_{ano}",
    )
    _q_conc = busca_conc.strip().lower()

    def _conc_match(texto: str) -> bool:
        return not _q_conc or _q_conc in texto.lower()

    # ── Automáticos ───────────────────────────────────────────────────────────
    if n_auto > 0:
        st.markdown(f"**🤖 {n_auto} automáticos** — selecione linha(s) e clique em Desvincular")
        auto_rows, auto_actions = [], []
        # Usa apenas os índices realmente matchados (não só chaves_auto_counts)
        _sp_auto_df = sponte_df[sponte_df.index.isin(_sp_idx_auto)]
        _bk_auto_df = banco_df_full[banco_df_full.index.isin(_bk_idx_auto)]
        for chave in sorted(_sp_auto_df["chave"].unique()):
            sp_matches = _sp_auto_df[_sp_auto_df["chave"] == chave]
            bk_matches = _bk_auto_df[_bk_auto_df["chave"] == chave]
            for i in range(min(len(sp_matches), len(bk_matches))):
                sp_r, bk_r = sp_matches.iloc[i], bk_matches.iloc[i]
                sp_txt_v = _sp_txt(sp_r["chave"])
                bk_txt_v = _bk_txt(bk_r["chave"])
                if not _conc_match(sp_txt_v) and not _conc_match(bk_txt_v):
                    continue
                auto_rows.append({"🔵 Sponte": sp_txt_v, "🏦 Banco": bk_txt_v})
                auto_actions.append((sp_r["chave"], bk_r["chave"]))

        sel_a = st.dataframe(
            pd.DataFrame(auto_rows),
            use_container_width=True,
            height=min(500, 38 + 35 * len(auto_rows)),
            hide_index=True,
            selection_mode="multi-row",
            on_select="rerun",
            key=f"df_auto_{mes}_{ano}",
        )
        sel_a_rows = sel_a.selection.rows if hasattr(sel_a, "selection") else []
        # filtra índices fora do range (podem ocorrer quando a pesquisa muda)
        sel_a_rows = [i for i in sel_a_rows if i < len(auto_actions)]
        if sel_a_rows:
            if st.button(f"🔓 Desvincular {len(sel_a_rows)} selecionado(s)", type="primary"):
                for idx in sel_a_rows:
                    sp_ch, bk_ch = auto_actions[idx]
                    db.salvar_conciliacao(mes, ano, "desvincular",
                                          sponte_chave=sp_ch, banco_chave=bk_ch)
                st.rerun()

    # ── Manuais ───────────────────────────────────────────────────────────────
    if n_manual > 0:
        st.markdown(f"**🔗 {n_manual} manuais** — selecione linha(s) e clique em Desvincular")
        manual_df = conc_df[conc_df["tipo"] == "manual"].copy()
        shown_ids: set = set()
        manual_rows, manual_actions = [], []

        # N:1
        bk_counts = manual_df["banco_chave"].value_counts()
        for bk_chave in bk_counts[bk_counts > 1].index:
            grupo = manual_df[manual_df["banco_chave"] == bk_chave]
            ids_grupo = grupo["id"].tolist()
            shown_ids.update(ids_grupo)
            sp_txt = " + ".join(_sp_txt(c["sponte_chave"]) for _, c in grupo.iterrows())
            bk_txt_v = _bk_txt(bk_chave)
            if not _conc_match(sp_txt) and not _conc_match(bk_txt_v):
                continue
            manual_rows.append({"🔵 Sponte": sp_txt, "🏦 Banco": bk_txt_v})
            manual_actions.append(ids_grupo)

        # 1:N novo formato (§§)
        restante = manual_df[~manual_df["id"].isin(shown_ids)]
        for _, c in restante.iterrows():
            bk_raw = str(c.get("banco_chave", ""))
            if "§§" not in bk_raw:
                continue
            shown_ids.add(c["id"])
            bk_lista = [ch.strip() for ch in bk_raw.split("§§") if ch.strip()]
            bk_txt = " + ".join(_bk_txt(ch) for ch in bk_lista)
            sp_txt_v = _sp_txt(c["sponte_chave"])
            if not _conc_match(sp_txt_v) and not _conc_match(bk_txt):
                continue
            manual_rows.append({"🔵 Sponte": sp_txt_v, "🏦 Banco": bk_txt})
            manual_actions.append([c["id"]])

        # 1:N formato antigo
        restante = manual_df[~manual_df["id"].isin(shown_ids)]
        sp_counts2 = restante["sponte_chave"].value_counts()
        for sp_chave in sp_counts2[sp_counts2 > 1].index:
            grupo = restante[restante["sponte_chave"] == sp_chave]
            ids_grupo = grupo["id"].tolist()
            shown_ids.update(ids_grupo)
            bk_txt = " + ".join(_bk_txt(c["banco_chave"]) for _, c in grupo.iterrows())
            sp_txt_v = _sp_txt(sp_chave)
            if not _conc_match(sp_txt_v) and not _conc_match(bk_txt):
                continue
            manual_rows.append({"🔵 Sponte": sp_txt_v, "🏦 Banco": bk_txt})
            manual_actions.append(ids_grupo)

        # 1:1
        for _, c in manual_df[~manual_df["id"].isin(shown_ids)].iterrows():
            sp_txt_v = _sp_txt(c["sponte_chave"])
            bk_txt_v = _bk_txt(c["banco_chave"])
            if not _conc_match(sp_txt_v) and not _conc_match(bk_txt_v):
                continue
            manual_rows.append({"🔵 Sponte": sp_txt_v, "🏦 Banco": bk_txt_v})
            manual_actions.append([c["id"]])

        if manual_rows:
            sel_m = st.dataframe(
                pd.DataFrame(manual_rows),
                use_container_width=True,
                height=min(400, 38 + 35 * len(manual_rows)),
                hide_index=True,
                selection_mode="multi-row",
                on_select="rerun",
                key=f"df_manual_{mes}_{ano}",
            )
            sel_m_rows = sel_m.selection.rows if hasattr(sel_m, "selection") else []
            if sel_m_rows:
                if st.button(f"🔓 Desvincular {len(sel_m_rows)} selecionado(s)",
                             type="primary", key="btn_desv_m"):
                    for idx in sel_m_rows:
                        for id_c in manual_actions[idx]:
                            db.deletar_conciliacao(int(id_c))
                    st.rerun()

    # ── Ignorados ─────────────────────────────────────────────────────────────
    if n_ign > 0:
        st.markdown(f"**🙈 {n_ign} ignorados**")
        ign_df = conc_df[conc_df["tipo"].str.startswith("ignorado", na=False)]
        ign_rows, ign_ids = [], []
        for _, c in ign_df.iterrows():
            just = f" · {c['justificativa']}" if c.get("justificativa") else ""
            if c["tipo"] == "ignorado_sponte" and pd.notna(c.get("sponte_chave")):
                txt = _sp_txt(c["sponte_chave"]) + just
            else:
                txt = _bk_txt(c.get("banco_chave", "")) + just
            if not _conc_match(txt):
                continue
            ign_rows.append({"Item": txt})
            ign_ids.append(c["id"])

        sel_i = st.dataframe(
            pd.DataFrame(ign_rows),
            use_container_width=True,
            height=min(300, 38 + 35 * len(ign_rows)),
            hide_index=True,
            selection_mode="multi-row",
            on_select="rerun",
            key=f"df_ign_{mes}_{ano}",
        )
        sel_i_rows = sel_i.selection.rows if hasattr(sel_i, "selection") else []
        if sel_i_rows:
            if st.button(f"🗑️ Remover {len(sel_i_rows)} selecionado(s)", key="btn_rem_i"):
                for idx in sel_i_rows:
                    db.deletar_conciliacao(int(ign_ids[idx]))
                st.rerun()

# ── Zona de perigo — limpar toda a conciliação do mês ────────────────────────
st.divider()
total_conc = n_auto + n_manual + n_ign
with st.expander("🗑️ Limpar conciliação do mês", expanded=False):
    if total_conc == 0:
        st.info("Nenhuma conciliação registrada para este mês.")
    else:
        st.warning(
            f"Isso vai apagar **todos os {total_conc} registros** de conciliação "
            f"de **{MESES_ABREV[mes]}/{ano}** ({n_auto} automáticos · "
            f"{n_manual} manuais · {n_ign} ignorados). "
            f"Use antes de reimportar o mês."
        )
        confirmar = st.checkbox("Sim, quero apagar todas as conciliações deste mês")
        if confirmar:
            if st.button("🗑️ Limpar tudo", type="primary", use_container_width=True):
                db.limpar_conciliacoes_mes(mes, ano)
                st.success("Conciliações apagadas! Agora você pode reimportar o mês com segurança.")
                st.rerun()
