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

import unicodedata as _ucd

def _norm_nome(s: str) -> str:
    """Normaliza nome para comparação: minúsculas sem acentos."""
    s = _ucd.normalize("NFD", str(s).lower().strip())
    return "".join(c for c in s if _ucd.category(c) != "Mn")

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
# Guarda o tamanho do banco original para reindexar o caixa igual ao banco_df_full
_n_banco_orig = len(banco_df)
if usar_caixa and not usar_banco:
    if _caixa_adaptado.empty:
        st.info("Nenhum lançamento de caixa importado para este mês. Use **📥 Importar Mês** para carregar a planilha de caixa.")
        st.stop()
    banco_df = _caixa_adaptado.copy()
    # Alinha índices com os do banco_df_full (caixa começa depois do banco)
    banco_df.index = range(_n_banco_orig, _n_banco_orig + len(banco_df))
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
    # Trata múltiplos alunos separados por vírgula (ex: "Bernardo Rosa, Julio Rosa")
    partes = [p.strip() for p in str(nome_aluno).replace(";", ",").split(",") if p.strip()]
    resps = []
    for parte in partes:
        key = _norm_nome(parte)
        if key in _aluno_resp_map:
            resps.append(_aluno_resp_map[key])
            continue
        for k, v in _aluno_resp_map.items():
            if k.startswith(key + " "):
                resps.append(v)
                break
    if resps:
        # Une responsáveis únicos
        _todos = []
        for r in resps:
            for nome in r.split(" / "):
                if nome not in _todos:
                    _todos.append(nome)
        return " / ".join(_todos)
    return ""

def _aluno_do_responsavel(nome_resp: str) -> str:
    key = _norm_nome(nome_resp)
    if key in _resp_aluno_map:
        return _resp_aluno_map[key]
    for k, v in _resp_aluno_map.items():
        if k.startswith(key + " "):
            return v
    return ""


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
    if nome:
        nome_n = _norm_nome(nome)
        # Caso 1: banco trouxe nome do aluno → pega o primeiro responsável
        resp_via_aluno = _aluno_resp_map.get(nome_n, "")
        if resp_via_aluno:
            nome_norm = _norm_nome(resp_via_aluno.split(" / ")[0])
        else:
            # Caso 2: banco trouxe nome de um responsável (pode ser o 2º, 3º…)
            # → busca o aluno dele e usa o primeiro responsável canônico
            aluno_via_resp = _resp_aluno_map.get(nome_n, "")
            if aluno_via_resp:
                primeiro_aluno = aluno_via_resp.split(" / ")[0]
                resp_canonica = _aluno_resp_map.get(_norm_nome(primeiro_aluno), "")
                nome_norm = _norm_nome(resp_canonica.split(" / ")[0]) if resp_canonica else nome_n
            else:
                nome_norm = nome_n
    else:
        nome_norm = ""
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


# ── Sugestões fuzzy (N→1, data ±5 dias, valor ±R$0,50) ───────────────────────
_TOLE_DIAS = 5
_TOLE_VAL  = 0.50

def _resp_canonico(nome: str) -> str:
    n = _norm_nome(str(nome))
    resp = _aluno_resp_map.get(n, "")
    if resp:
        return _norm_nome(resp.split(" / ")[0])
    aluno = _resp_aluno_map.get(n, "")
    if aluno:
        r2 = _aluno_resp_map.get(_norm_nome(aluno.split(" / ")[0]), "")
        if r2:
            return _norm_nome(r2.split(" / ")[0])
    return n

def _parse_d(v):
    try:
        import datetime as _dt
        if isinstance(v, _dt.date):
            return v
        return pd.to_datetime(str(v), dayfirst=True).date()
    except Exception:
        return None

_sug_ignoradas = set()
for _, _r in conc_df.iterrows():
    if _r.get("tipo") == "sugestao_ignorada":
        _sk = str(_r.get("sponte_chave") or "")
        _bk = str(_r.get("banco_chave") or "")
        for _s in _sk.split("§§"):
            if _s.strip():
                _sug_ignoradas.add((_s.strip(), _bk))

sugestoes: list[dict] = []
_sp_chaves_em_sug: set = set()
_bk_chaves_em_sug: set = set()

from itertools import combinations as _combins

for _bk_i, _bk_r in banco_pendente.iterrows():
    _bk_ch = _bk_r["chave"]
    if _bk_ch in _bk_chaves_em_sug:
        continue
    _bk_val  = float(_bk_r["valor"])
    _bk_dt   = _parse_d(_bk_r["data_mov"])
    _bk_nome = _resp_canonico(str(_bk_r.get("origem_destino", "") or ""))
    _bk_es   = _bk_r["deb_cred"]

    _cands = []
    for _sp_i, _sp_r in sponte_pendente.iterrows():
        if _sp_r["chave"] in _sp_chaves_em_sug:
            continue
        if _sp_r["es"] != _bk_es:
            continue
        _sp_nome = _resp_canonico(str(_sp_r.get("origem_destino", "") or ""))
        if _bk_nome and _sp_nome:
            if _bk_nome != _sp_nome and _bk_nome not in _sp_nome and _sp_nome not in _bk_nome:
                continue
        _sp_dt = _parse_d(_sp_r["data"])
        if _bk_dt and _sp_dt and abs((_bk_dt - _sp_dt).days) > _TOLE_DIAS:
            continue
        _cands.append((_sp_i, _sp_r, float(_sp_r["valor"])))

    if not _cands:
        continue

    # 1→1 tolerância de valor (e/ou data)
    _found = False
    for _si, _sr, _sv in _cands:
        if abs(_sv - _bk_val) <= _TOLE_VAL and _sr["chave"] != _bk_ch:
            _key = (_sr["chave"], _bk_ch)
            if _key not in _sug_ignoradas:
                sugestoes.append({
                    "tipo": "1→1",
                    "sp_rows": [(_si, _sr)],
                    "bk_i": _bk_i, "bk_r": _bk_r,
                    "diff_val": abs(_sv - _bk_val),
                })
                _sp_chaves_em_sug.add(_sr["chave"])
                _bk_chaves_em_sug.add(_bk_ch)
                _found = True
            break
    if _found:
        continue

    # N→1: combinações de candidatos cuja soma ≈ bk_val
    for _nc in [2, 3]:
        if len(_cands) < _nc:
            continue
        _found2 = False
        for _combo in _combins(_cands, _nc):
            _soma = sum(v for _, _, v in _combo)
            if abs(_soma - _bk_val) <= _TOLE_VAL:
                _sp_chs = "§§".join(_r["chave"] for _, _r, _ in _combo)
                _key2 = (_sp_chs, _bk_ch)
                if _key2 not in _sug_ignoradas:
                    sugestoes.append({
                        "tipo": f"{_nc}→1",
                        "sp_rows": [(_i, _r) for _i, _r, _ in _combo],
                        "bk_i": _bk_i, "bk_r": _bk_r,
                        "diff_val": abs(_soma - _bk_val),
                    })
                    for _, _r, _ in _combo:
                        _sp_chaves_em_sug.add(_r["chave"])
                    _bk_chaves_em_sug.add(_bk_ch)
                    _found2 = True
                break
        if _found2:
            break


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

        # ── Sugestões fuzzy ───────────────────────────────────────────────────
        _cnt_sug = st.session_state.get("conc_cnt", 0)
        if sugestoes:
            with st.expander(f"💡 **{len(sugestoes)} sugestão(ões) de vínculo** — data, valor ou quantidade aproximados", expanded=True):
                for _idx_sug, _sug in enumerate(sugestoes):
                    _bk_r2 = _sug["bk_r"]
                    _sp_rows2 = _sug["sp_rows"]
                    _tipo_sug = _sug["tipo"]
                    _diff_val = _sug["diff_val"]

                    with st.container(border=True):
                        _sc1, _sc2 = st.columns([6, 2])
                        with _sc1:
                            st.caption(f"Sugestão {_tipo_sug}" + (f" · diferença R$ {_diff_val:.2f}" if _diff_val > 0 else ""))
                            for _, _sp_r2 in _sp_rows2:
                                _sp_dt2 = pd.to_datetime(_sp_r2["data"]).strftime("%d/%m") if pd.notna(_sp_r2.get("data")) else "—"
                                _sp_aluno2 = str(_sp_r2.get("origem_destino", ""))
                                _sp_resp2  = _responsavel_do_aluno(_sp_aluno2)
                                _sp_nome2  = f"{_sp_aluno2}" + (f" ({_sp_resp2})" if _sp_resp2 and _sp_resp2 != _sp_aluno2 else "")
                                st.markdown(
                                    f"🔵 **Sponte** {_sp_dt2} · {_sp_r2['es']} · "
                                    f"**R$ {float(_sp_r2['valor']):,.2f}** · {_sp_nome2}"
                                )
                            _bk_dt2   = str(_bk_r2["data_mov"])[:5] if _bk_r2.get("data_mov") else "—"
                            _bk_nome2 = str(_bk_r2.get("origem_destino", "") or "")
                            _bk_aluno2 = _aluno_do_responsavel(_bk_nome2)
                            _bk_label2 = f"{_bk_nome2}" + (f" (aluno: {_bk_aluno2})" if _bk_aluno2 else "")
                            st.markdown(
                                f"🏦 **Banco** {_bk_dt2} · {_bk_r2['deb_cred']} · "
                                f"**R$ {float(_bk_r2['valor']):,.2f}** · {_bk_label2}"
                            )
                        with _sc2:
                            _just_key = f"sug_just_{_idx_sug}_{_cnt_sug}"
                            if _diff_val > 0:
                                _just_sug = st.text_input(
                                    "Justificativa (obrigatória):",
                                    placeholder="ex: arredondamento, taxa bancária…",
                                    key=_just_key,
                                )
                            else:
                                _just_sug = f"Sugestão {_tipo_sug}"
                            _just_invalida = _diff_val > 0 and not (_just_sug or "").strip()
                            if st.button("✅ Confirmar", key=f"sug_ok_{_idx_sug}_{_cnt_sug}", use_container_width=True, type="primary", disabled=_just_invalida):
                                _just_final = (_just_sug or "").strip() or f"Sugestão {_tipo_sug}"
                                for _, _sp_r2 in _sp_rows2:
                                    db.salvar_conciliacao(mes, ano, "manual",
                                                          sponte_chave=_sp_r2["chave"],
                                                          banco_chave=_bk_r2["chave"],
                                                          justificativa=_just_final)
                                st.session_state["conc_cnt"] = _cnt_sug + 1
                                st.rerun()
                            if st.button("✕ Ignorar", key=f"sug_no_{_idx_sug}_{_cnt_sug}", use_container_width=True):
                                _sp_chs2 = "§§".join(_r2["chave"] for _, _r2 in _sp_rows2)
                                db.salvar_conciliacao(mes, ano, "sugestao_ignorada",
                                                      sponte_chave=_sp_chs2,
                                                      banco_chave=_bk_r2["chave"])
                                st.session_state["conc_cnt"] = _cnt_sug + 1
                                st.rerun()

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
        _alu_cfg  = st.column_config.TextColumn("Origem/Destino", width=180)
        _resp_cfg = st.column_config.TextColumn("Responsável",  width=180)
        _his_cfg  = st.column_config.TextColumn("Histórico",    width=130)

        _resp_series = sp_filtrado["origem_destino"].apply(_responsavel_do_aluno)
        sp_show_full = pd.DataFrame({
            "Data":        pd.to_datetime(sp_filtrado["data"]).dt.strftime("%d/%m"),
            "E/S":         sp_filtrado["es"],
            "Valor":       sp_filtrado["valor"].abs(),
            "Categoria":   sp_filtrado["categoria"],
            "Origem/Destino":       sp_filtrado["origem_destino"],
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
            Se múltiplos alunos separados por vírgula → junta responsáveis comuns.
            Se nenhum dos dois     → ('', nome).
            """
            if not nome or nome.lower() == "nan":
                return "", ""
            # Tenta lookup direto primeiro
            aluno = _aluno_do_responsavel(nome)
            if aluno:
                return aluno, nome
            resp = _responsavel_do_aluno(nome)
            if resp:
                return nome, resp
            # Múltiplos alunos separados por vírgula (ex: "Bernardo Rosa, Julio Rosa")
            partes = [p.strip() for p in nome.split(",") if p.strip()]
            if len(partes) > 1:
                resps_encontrados = []
                alunos_encontrados = []
                for parte in partes:
                    r = _responsavel_do_aluno(parte)
                    if r:
                        alunos_encontrados.append(parte)
                        for rr in r.split(" / "):
                            if rr not in resps_encontrados:
                                resps_encontrados.append(rr)
                if alunos_encontrados:
                    return " / ".join(alunos_encontrados), " / ".join(resps_encontrados)
            return "", nome                 # desconhecido → só responsável

        _bk_aluno_col  = _bk_nome.apply(lambda n: _bk_aluno_resp(n)[0])
        _bk_resp_col   = _bk_nome.apply(lambda n: _bk_aluno_resp(n)[1])

        bk_show_full = pd.DataFrame({
            "Data":        bk_filtrado["data_fmt"].str[:5],
            "E/S":         bk_filtrado["deb_cred"],
            "Valor":       bk_filtrado["valor"].abs(),
            "Origem/Destino":       _bk_aluno_col,
            "Responsável": _bk_resp_col,
            "Histórico":   bk_filtrado["historico"],
        })

        # ── Defaults de configuração de tabela ───────────────────────────────
        _SP_COLS_DEF = ["Data", "E/S", "Valor", "Categoria", "Origem/Destino", "Responsável"]
        _BK_COLS_DEF = ["Data", "E/S", "Valor", "Origem/Destino", "Responsável", "Histórico"]
        _SP_SORT_DEF = "Data"
        _BK_SORT_DEF = "Origem/Destino"

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
                "Ordenar por", ["Data","Valor","Categoria","Origem/Destino","Responsável"],
                index=["Data","Valor","Categoria","Origem/Destino","Responsável"].index(
                    st.session_state[f"sp_sort_{_sk}"] if st.session_state[f"sp_sort_{_sk}"] in ["Data","Valor","Categoria","Origem/Destino","Responsável"] else "Data"
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
                    "Categoria": _cat_cfg, "Origem/Destino": _alu_cfg, "Responsável": _resp_cfg,
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
                "Ordenar por", ["Data","Valor","Origem/Destino","Responsável","Histórico"],
                index=["Data","Valor","Origem/Destino","Responsável","Histórico"].index(
                    st.session_state[f"bk_sort_{_sk}"] if st.session_state[f"bk_sort_{_sk}"] in ["Data","Valor","Origem/Destino","Responsável","Histórico"] else "Data"
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
                    "Origem/Destino": _alu_cfg, "Responsável": _resp_cfg, "Histórico": _his_cfg,
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
            st.markdown('<div style="height:188px"></div>', unsafe_allow_html=True)
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
                        "Selecione o motivo…",
                        "Divergência de valor",
                        "Diferença de centavos / arredondamento",
                        "Desconto concedido",
                        "Juros / multa por atraso",
                        "Pagamento parcial",
                        "Complemento de pagamento anterior",
                        "Agrupamento de pagamentos",
                        "Pagamento agrupado (vários alunos)",
                        "Pagamento agrupado com diferença",
                        "Outros",
                        "Erro de lançamento no Sponte",
                        "FGTS / rescisão — não operacional",
                        "Outro motivo…",
                    ]
                    _justificativa = None
                    if diff > 0.02:
                        st.warning(f"⚠️ Dif: {_md_val(diff)}")
                        _justificativa = st.selectbox(
                            "Motivo:", _MOTIVOS_DIF,
                            key=f"motivo_dif_{cnt}",
                        )
                        if _justificativa == "Outro motivo…":
                            _outro_dif = st.text_input(
                                "Descreva:", placeholder="ex: FGTS rescisão — compensado internamente",
                                key=f"outro_dif_{cnt}",
                            )
                            _justificativa = _outro_dif.strip() or "Outro motivo"
                        _just_invalida_dif = _justificativa == "Selecione o motivo…"
                    else:
                        _just_invalida_dif = False

                    if n_sp > 1:
                        lbl = f"🔗 Vincular {n_sp}→1"
                    elif n_bk > 1:
                        lbl = f"🔗 Vincular 1→{n_bk}"
                    else:
                        lbl = "🔗 Vincular"
                    if st.button(lbl, type="primary", use_container_width=True, disabled=_just_invalida_dif):
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

                st.caption("*Selecione Banco(s) para vincular, ou ignore:*")
                _MOTIVOS_LISTA = [
                    "Selecione o motivo…",
                    "🚨 Valor Desviado",
                    "Desconto em folha",
                    "Pago em caixa físico",
                    "Estorno/Cancelamento",
                    "Pagamento não localizado",
                    "Outro motivo…",
                ]
                _mot_sel = st.selectbox(
                    "Motivo:", _MOTIVOS_LISTA,
                    key=f"motivo_ign_{cnt}",
                    label_visibility="collapsed",
                )
                _outro_txt = ""
                if _mot_sel == "Outro motivo…":
                    _outro_txt = st.text_input(
                        "Descreva:", placeholder="ex: negociação direta",
                        key=f"outro_ign_{cnt}",
                    )
                _mot_invalido = _mot_sel == "Selecione o motivo…"
                _lbl_ign_sp = f"🙈 Ignorar {n_sp} itens" if n_sp > 1 else "🙈 Ignorar Sponte"
                if st.button(_lbl_ign_sp, key=f"btn_ign_{cnt}",
                             use_container_width=True,
                             disabled=_mot_invalido):
                    _just = _outro_txt.strip() if _mot_sel == "Outro motivo…" else _mot_sel
                    for _sp_r in sp_selecionados:
                        db.salvar_conciliacao(mes, ano, "ignorado_sponte",
                                              sponte_chave=_sp_r["chave"],
                                              justificativa=_just or None)
                    st.session_state["conc_cnt"] += 1
                    st.rerun()

            elif n_bk > 0:
                # ── Só Banco selecionado ──────────────────────────────────────
                bk_selecionados = [bk_filtrado.loc[i] for i in bk_sel_rows]
                for r in bk_selecionados:
                    st.caption(f"🏦 {str(r['historico'])[:22]}  \n**{_md_val(float(r['valor']))}**")
                if n_bk > 1:
                    soma_bk = sum(abs(float(r["valor"])) for r in bk_selecionados)
                    st.markdown(
                        f"<span style='font-size:0.9rem;color:#888;font-weight:700'>"
                        f"Total {_html_val(soma_bk)}</span>",
                        unsafe_allow_html=True,
                    )
                st.caption("*Selecione Sponte para vincular, ou ignore:*")
                _MOTIVOS_BANCO = [
                    "Selecione o motivo…",
                    "Origem desconhecida",
                    "Não lançado no Sponte",
                    "Aplicação Financeira",
                    "Resgate Financeiro",
                    "Tarifa/Taxa bancária",
                    "Estorno/Cancelamento",
                    "Outro motivo…",
                ]
                _mot_bk = st.selectbox(
                    "Motivo:", _MOTIVOS_BANCO,
                    key=f"motivo_bk_{cnt}",
                    label_visibility="collapsed",
                )
                _outro_bk = ""
                if _mot_bk == "Outro motivo…":
                    _outro_bk = st.text_input(
                        "Descreva:", placeholder="ex: depósito identificado depois",
                        key=f"outro_bk_{cnt}",
                    )
                _bk_invalido = _mot_bk == "Selecione o motivo…"
                _lbl_ign_bk = f"🙈 Ignorar {n_bk} itens" if n_bk > 1 else "🙈 Ignorar Banco"
                if st.button(_lbl_ign_bk, key=f"btn_ign_bk_{cnt}",
                             use_container_width=True,
                             disabled=_bk_invalido):
                    _just_bk = _outro_bk.strip() if _mot_bk == "Outro motivo…" else _mot_bk
                    for r in bk_selecionados:
                        db.salvar_conciliacao(mes, ano, "ignorado_banco",
                                              banco_chave=r["chave"],
                                              justificativa=_just_bk or None)
                    st.session_state["conc_cnt"] += 1
                    st.rerun()

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
            sel_m_rows = [idx for idx in sel_m_rows if idx < len(manual_actions)]
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
        sel_i_rows = [idx for idx in sel_i_rows if idx < len(ign_ids)]
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
        _ck_key = f"confirmar_limpar_{mes}_{ano}"
        confirmar = st.checkbox("Sim, quero apagar todas as conciliações deste mês", key=_ck_key)
        if confirmar:
            if st.button("🗑️ Limpar tudo", type="primary", use_container_width=True):
                db.limpar_conciliacoes_mes(mes, ano)
                st.cache_data.clear()
                st.session_state["limpar_ok"] = f"{MESES_ABREV[mes]}/{ano}"
                st.rerun()

_limpar_ok = st.session_state.pop("limpar_ok", None)
if _limpar_ok:
    st.success(f"✅ Conciliações de {_limpar_ok} apagadas com sucesso!")

# ── Resumo Financeiro ─────────────────────────────────────────────────────────
st.divider()
st.markdown("### 📊 Resumo Financeiro")

# Totais do Fluxo de Caixa Sponte
_sp_e = sponte_df[sponte_df["es"] == "E"]["valor"].sum()
_sp_s = sponte_df[sponte_df["es"] == "S"]["valor"].sum()

# Totais do Banco + Caixa
_bk_e = banco_df_full[banco_df_full["deb_cred"] == "E"]["valor"].sum() if not banco_df_full.empty else 0.0
_bk_s = banco_df_full[banco_df_full["deb_cred"] == "S"]["valor"].sum() if not banco_df_full.empty else 0.0

_col1, _col2 = st.columns(2)
with _col1:
    st.markdown("**📋 Fluxo de Caixa Sponte**")
    st.metric("Entradas previstas", fmt_br(_sp_e))
    st.metric("Saídas previstas",   fmt_br(_sp_s))
    st.metric("Saldo previsto",     fmt_br(_sp_e - _sp_s))

with _col2:
    st.markdown(f"**{_titulo_extrato}**")
    st.metric("Entradas realizadas", fmt_br(_bk_e))
    st.metric("Saídas realizadas",   fmt_br(_bk_s))
    st.metric("Saldo realizado",     fmt_br(_bk_e - _bk_s))

# Diferença explicada pelos ignorados
st.markdown("**🔍 Diferença explicada** — selecione uma linha para ver os detalhes")

_MOTIVO_ICONS = {
    "Valor Desviado":           "🚨",
    "Desconto em folha":        "📝",
    "Pago em caixa físico":     "💵",
    "Estorno/Cancelamento":     "↩️",
    "Pagamento não localizado": "❓",
    "Origem desconhecida":      "❓",
    "Não lançado no Sponte":    "📭",
    "Aplicação Financeira":     "💹",
    "Resgate Financeiro":       "💹",
    "Tarifa/Taxa bancária":     "🏦",
    "Sem motivo":               "📋",
}

def _mot_label(v):
    """Normaliza justificativa nula/nan para 'Sem motivo'."""
    s = str(v).strip() if v is not None else ""
    return s if s and s.lower() != "nan" else "Sem motivo"

# ── Monta estrutura de dados agrupada ────────────────────────────────────────
_sp_ign_rows = conc_df[conc_df["tipo"] == "ignorado_sponte"].copy()
_bk_ign_rows = conc_df[conc_df["tipo"] == "ignorado_banco"].copy()

# Vínculos manuais com divergência de valor (Sponte ≠ Banco)
# Agrupa por banco_chave para tratar N Sponte → 1 Banco corretamente
_manuais_rows = conc_df[conc_df["tipo"] == "manual"].copy()
_divergencias = []   # (ids, sp_txts, bk_txt, sp_total, bk_total, diff, justificativa)
_grupos_bk: dict = {}   # banco_chave → lista de linhas manuais
for _, _mrow in _manuais_rows.iterrows():
    _bk_ch = _mrow.get("banco_chave") or ""
    _grupos_bk.setdefault(_bk_ch, []).append(_mrow)

for _bk_ch, _grupo in _grupos_bk.items():
    if not _bk_ch:
        continue
    _bk_chs = [c.strip() for c in str(_bk_ch).split("§§") if c.strip()]
    _bk_total = sum(
        abs(float(banco_df_full[banco_df_full["chave"] == c].iloc[0]["valor"]))
        for c in _bk_chs if not banco_df_full[banco_df_full["chave"] == c].empty
    )
    _sp_total = 0.0
    _sp_txts, _ids, _justs = [], [], []
    for _mrow in _grupo:
        _sp_ch = _mrow.get("sponte_chave")
        if not _sp_ch:
            continue
        _sp_r = sponte_df[sponte_df["chave"] == _sp_ch]
        if _sp_r.empty:
            continue
        _sp_total += abs(float(_sp_r.iloc[0]["valor"]))
        _sp_txts.append(_sp_txt(_sp_ch))
        _ids.append(_mrow["id"])
        _j = _mrow.get("justificativa")
        if _j and str(_j).strip() and str(_j).strip() not in ("Sugestão 1→1", "Sugestão 2→1", "Sugestão 3→1"):
            _justs.append(str(_j).strip())
    _diff = round(_sp_total - _bk_total, 2)
    if abs(_diff) > 0.01 and _ids:
        _bk_label = _bk_txt(_bk_chs[0]) if _bk_chs else _bk_ch
        _just_div = _justs[0] if _justs else ""
        _divergencias.append((_ids, _sp_txts, _bk_label, _sp_total, _bk_total, _diff, _just_div))

_sp_por_motivo: dict = {}
for _, _irow in _sp_ign_rows.iterrows():
    _ch = _irow.get("sponte_chave")
    if not _ch:
        continue
    _r = sponte_df[sponte_df["chave"] == _ch]
    _v = abs(float(_r.iloc[0]["valor"])) if not _r.empty else 0.0
    _txt = _sp_txt(_ch) if not _r.empty else str(_ch)
    _mot = _mot_label(_irow.get("justificativa"))
    _sp_por_motivo.setdefault(_mot, []).append((_irow["id"], _ch, _txt, _v))

_bk_por_motivo: dict = {}
for _, _irow in _bk_ign_rows.iterrows():
    _ch = _irow.get("banco_chave")
    if not _ch:
        continue
    _r = banco_df_full[banco_df_full["chave"] == _ch]
    _v_abs = abs(float(_r.iloc[0]["valor"])) if not _r.empty else 0.0
    _sinal_bk = -1 if (not _r.empty and str(_r.iloc[0].get("deb_cred","E")) == "S") else 1
    _v = _v_abs * _sinal_bk
    _txt = _bk_txt(_ch) if not _r.empty else str(_ch)
    _mot = _mot_label(_irow.get("justificativa"))
    _bk_por_motivo.setdefault(_mot, []).append((_irow["id"], _ch, _txt, _v))

_sp_pend_total = sponte_pendente["valor"].abs().sum()
_bk_pend_total = banco_pendente["valor"].abs().sum() if not banco_pendente.empty else 0.0

# ── Tabela resumo (selecionável) ──────────────────────────────────────────────
_resumo_rows = []
_resumo_meta = []   # guarda tipo e motivo para detalhar ao selecionar

if _divergencias:
    _div_sem_motivo = [d for d in _divergencias if not d[6]]
    _div_com_motivo: dict = {}
    for _d in _divergencias:
        if _d[6]:
            _div_com_motivo.setdefault(_d[6], []).append(_d)
    if _div_sem_motivo:
        _div_total = sum(d[5] for d in _div_sem_motivo)
        _sinal_div = "+" if _div_total >= 0 else ""
        _resumo_rows.append({"Motivo": "⚖️ Divergência em vínculos manuais", "Valor (R$)": f"{_sinal_div}{fmt_br(_div_total)}", "Itens": len(_div_sem_motivo)})
        _resumo_meta.append(("divergencia", ""))
    for _dmot, _ditens in sorted(_div_com_motivo.items(), key=lambda x: -sum(abs(d[5]) for d in x[1])):
        _dtotal = sum(d[5] for d in _ditens)
        _sinal_dm = "+" if _dtotal >= 0 else ""
        _resumo_rows.append({"Motivo": f"⚖️ {_dmot}", "Valor (R$)": f"{_sinal_dm}{fmt_br(_dtotal)}", "Itens": len(_ditens)})
        _resumo_meta.append(("divergencia", _dmot))

for _mot, _itens in sorted(_sp_por_motivo.items(), key=lambda x: -abs(sum(i[3] for i in x[1]))):
    _icon = _MOTIVO_ICONS.get(_mot, "📋")
    _total = sum(i[3] for i in _itens)
    _sinal_str = "+" if _total >= 0 else ""
    _resumo_rows.append({"Motivo": f"{_icon} {_mot}", "Valor (R$)": f"{_sinal_str}{fmt_br(_total)}", "Itens": len(_itens)})
    _resumo_meta.append(("sponte", _mot))

for _mot, _itens in sorted(_bk_por_motivo.items(), key=lambda x: -abs(sum(i[3] for i in x[1]))):
    _icon = _MOTIVO_ICONS.get(_mot, "📋")
    _total = sum(i[3] for i in _itens)
    _sinal_str = "+" if _total >= 0 else ""
    _resumo_rows.append({"Motivo": f"{_icon} {_mot} (Banco)", "Valor (R$)": f"{_sinal_str}{fmt_br(_total)}", "Itens": len(_itens)})
    _resumo_meta.append(("banco", _mot))

if _sp_pend_total > 0:
    _resumo_rows.append({"Motivo": "⏳ Sponte pendente", "Valor (R$)": fmt_br(_sp_pend_total), "Itens": len(sponte_pendente)})
    _resumo_meta.append(("pend_sp", ""))
if _bk_pend_total > 0:
    _resumo_rows.append({"Motivo": "⏳ Banco/Caixa pendente", "Valor (R$)": fmt_br(_bk_pend_total), "Itens": len(banco_pendente)})
    _resumo_meta.append(("pend_bk", ""))

if not _resumo_rows:
    st.caption("Nenhum item ignorado ou pendente.")
else:
    _sel_res = st.dataframe(
        pd.DataFrame(_resumo_rows),
        use_container_width=True,
        hide_index=True,
        height=38 + 35 * len(_resumo_rows),
        selection_mode="single-row",
        on_select="rerun",
        key=f"df_resumo_{mes}_{ano}",
        column_config={
            "Itens": st.column_config.NumberColumn("Itens", width=60),
        },
    )
    _sel_res_rows = _sel_res.selection.rows if hasattr(_sel_res, "selection") else []

    if _sel_res_rows:
        _ri = _sel_res_rows[0]
        _tipo_sel, _mot_sel = _resumo_meta[_ri]
        st.markdown("---")

        _det_rows, _det_ids = [], []

        if _tipo_sel == "sponte" and _mot_sel in _sp_por_motivo:
            for _id, _ch, _txt, _v in _sp_por_motivo[_mot_sel]:
                _det_rows.append({"Item": f"🔵 {_txt}"})
                _det_ids.append([_id])

        elif _tipo_sel == "banco" and _mot_sel in _bk_por_motivo:
            for _id, _ch, _txt, _v in _bk_por_motivo[_mot_sel]:
                _det_rows.append({"Item": f"🏦 {_txt}"})
                _det_ids.append([_id])

        elif _tipo_sel == "pend_sp":
            for _, _pr in sponte_pendente.iterrows():
                _d = pd.to_datetime(_pr["data"]).strftime("%d/%m")
                _det_rows.append({"Item": f"🔵 {_d} · {_pr['categoria']} · {_pr.get('origem_destino','')} · {fmt_br(abs(_pr['valor']))}"})

        elif _tipo_sel == "pend_bk":
            for _, _pr in banco_pendente.iterrows():
                _nome = str(_pr.get("origem_destino","") or _pr.get("historico","")).strip()
                _det_rows.append({"Item": f"🏦 {str(_pr['data_fmt'])[:5]} · {_nome} · {fmt_br(abs(float(_pr['valor'])))}"})

        elif _tipo_sel == "divergencia":
            for _ids, _sp_txts, _bk_t, _sp_total, _bk_total, _diff, _just_d in _divergencias:
                if _mot_sel and _just_d != _mot_sel:
                    continue
                _sinal = "+" if _diff > 0 else "-"
                _sp_label = " + ".join(_sp_txts)
                _motivo = "Sponte maior que Banco" if _diff > 0 else "Banco maior que Sponte"
                _det_rows.append({
                    "Sponte": _sp_label,
                    "Banco": _bk_t,
                    "Sponte (R$)": fmt_br(_sp_total),
                    "Banco (R$)": fmt_br(_bk_total),
                    "Diferença": f"{_sinal} {fmt_br(abs(_diff))}",
                    "Motivo": _motivo,
                })
                _det_ids.append(list(_ids))  # type: ignore[arg-type]

        if _det_rows:
            _sel_det = st.dataframe(
                pd.DataFrame(_det_rows),
                use_container_width=True,
                hide_index=True,
                height=min(400, 38 + 35 * len(_det_rows)),
                selection_mode="multi-row",
                on_select="rerun",
                key=f"df_det_{mes}_{ano}_{_ri}",
            )
            _sel_det_rows = _sel_det.selection.rows if hasattr(_sel_det, "selection") else []
            _sel_det_rows = [i for i in _sel_det_rows if i < len(_det_ids)]
            if _sel_det_rows and _det_ids:
                if st.button(f"↩️ Desconciliar {len(_sel_det_rows)} selecionado(s)", type="primary"):
                    for _idx in _sel_det_rows:
                        for _id in _det_ids[_idx]:
                            db.deletar_conciliacao(int(_id))
                    st.rerun()
