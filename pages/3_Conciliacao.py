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

# ── Seleção de mês ─────────────────────────────────────────────────────────────
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

# ── Carrega dados ──────────────────────────────────────────────────────────────
sponte_df = db.carregar_lancamentos_sponte(mes, ano)
banco_df  = db.carregar_transacoes_banco(mes, ano)

if sponte_df.empty or banco_df.empty:
    st.warning("Dados de lançamentos não encontrados para este mês.")
    st.stop()


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
    dia_mes = f"{d.day:02d}/{d.month:02d}"   # DD/MM sem ano
    return f"{dia_mes}|{row['es']}|{float(row['valor']):.2f}".replace(".", ",")


def make_key_banco(row) -> str:
    dia_mes = str(row["data_mov"])[:5]        # "DD/MM/YYYY" → "DD/MM"
    return f"{dia_mes}|{row['deb_cred']}|{float(row['valor']):.2f}".replace(".", ",")


# ── Prepara DataFrames ─────────────────────────────────────────────────────────
sponte_df = sponte_df.copy()
banco_df  = banco_df.copy()
sponte_df["chave"]    = sponte_df.apply(make_key_sponte, axis=1)
banco_df["chave"]     = banco_df.apply(make_key_banco, axis=1)
banco_df["data_fmt"]  = banco_df["data_mov"].apply(_data_banco_fmt)

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
_cnt_bk = Counter(banco_df["chave"])

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
sp_manually_used_idx: set = set()
for _ch, _cnt in sp_manual_cnt.items():
    sp_manually_used_idx.update(sponte_df[sponte_df["chave"] == _ch].index[:_cnt].tolist())

bk_manually_used_idx: set = set()
for _ch, _cnt in bk_manual_cnt.items():
    bk_manually_used_idx.update(banco_df[banco_df["chave"] == _ch].index[:_cnt].tolist())

# Índices do auto-match (excluindo os já usados manualmente)
_sp_idx_auto: set = set()
_bk_idx_auto: set = set()
for _chave, _n in chaves_auto_counts.items():
    _sp_cands = sponte_df[
        (sponte_df["chave"] == _chave) & (~sponte_df.index.isin(sp_manually_used_idx))
    ]
    _bk_cands = banco_df[
        (banco_df["chave"] == _chave) & (~banco_df.index.isin(bk_manually_used_idx))
    ]
    _sp_idx_auto.update(_sp_cands.index[:_n].tolist())
    _bk_idx_auto.update(_bk_cands.index[:_n].tolist())

# ── Separa pendentes ───────────────────────────────────────────────────────────
mask_sp_ok = sponte_df.index.isin(_sp_idx_auto) | sponte_df.index.isin(sp_manually_used_idx)
mask_bk_ok = banco_df.index.isin(_bk_idx_auto)  | banco_df.index.isin(bk_manually_used_idx)
sponte_pendente = sponte_df[~mask_sp_ok].reset_index(drop=True)
banco_pendente  = banco_df[~mask_bk_ok].reset_index(drop=True)


# ── Barra de progresso ─────────────────────────────────────────────────────────
total_sp   = len(sponte_df)
total_bk   = len(banco_df)
total      = total_sp + total_bk
pendente   = len(sponte_pendente) + len(banco_pendente)
conciliado = total - pendente
pct        = conciliado / total if total else 0.0

st.markdown("### Progresso")
st.progress(
    pct,
    text=(
        f"**{conciliado} de {total}** itens conciliados ({pct:.0%}) — "
        f"{len(sponte_pendente)} Sponte + {len(banco_pendente)} Banco ainda pendentes"
    ),
)
st.divider()

# ── Seção: Conciliados ─────────────────────────────────────────────────────────
n_auto   = sum(chaves_auto_counts.values()) if chaves_auto_counts else 0
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

        # ── Filtro E/S ────────────────────────────────────────────────────────
        filtro_es = st.radio(
            "Filtrar por tipo:", ["Todos", "Entradas (E)", "Saídas (S)"],
            horizontal=True, key=f"filtro_es_{mes}_{ano}",
        )

        sp_filtrado = sponte_pendente.copy()
        bk_filtrado = banco_pendente.copy()
        if filtro_es == "Entradas (E)":
            sp_filtrado = sp_filtrado[sp_filtrado["es"] == "E"]
            bk_filtrado = bk_filtrado[bk_filtrado["deb_cred"] == "E"]
        elif filtro_es == "Saídas (S)":
            sp_filtrado = sp_filtrado[sp_filtrado["es"] == "S"]
            bk_filtrado = bk_filtrado[bk_filtrado["deb_cred"] == "S"]

        # Contador de ações — incrementar após cada ação reseta as seleções
        if "conc_cnt" not in st.session_state:
            st.session_state["conc_cnt"] = 0
        cnt    = st.session_state["conc_cnt"]
        sp_key = f"dfsp_{mes}_{ano}_{cnt}"
        bk_key = f"dfbk_{mes}_{ano}_{cnt}"

        col_sp, col_mid, col_bk = st.columns([5, 2, 5])

        _val_cfg  = st.column_config.NumberColumn("Valor", format="R$ %,.2f")
        _es_cfg   = st.column_config.TextColumn("E/S", width="small")
        _cat_cfg  = st.column_config.TextColumn("Categoria", width="medium")
        _orig_cfg = st.column_config.TextColumn("Origem/Destino", width="medium")

        sp_show = pd.DataFrame({
            "Data":           pd.to_datetime(sp_filtrado["data"]).dt.strftime("%d/%m"),
            "Categoria":      sp_filtrado["categoria"],          # sem corte → tooltip no hover
            "E/S":            sp_filtrado["es"],
            "Valor":          sp_filtrado["valor"].abs(),
            "Origem/Destino": sp_filtrado["origem_destino"],     # scroll para ver
        })

        bk_show = pd.DataFrame({
            "Data":      bk_filtrado["data_fmt"].str[:5],
            "Histórico": bk_filtrado["historico"],               # sem corte → tooltip no hover
            "E/S":       bk_filtrado["deb_cred"],
            "Valor":     bk_filtrado["valor"].abs(),
        })

        with col_sp:
            st.markdown("**📋 FluxoCaixa Sponte**")
            sel_sp = st.dataframe(
                sp_show,
                use_container_width=True,
                height=460,
                hide_index=True,
                column_config={
                    "Valor": _val_cfg,
                    "E/S": _es_cfg,
                    "Categoria": _cat_cfg,
                    "Origem/Destino": _orig_cfg,
                },
                selection_mode="multi-row",
                on_select="rerun",
                key=sp_key,
            )

        with col_bk:
            st.markdown("**🏦 Extrato Banco**")
            sel_bk = st.dataframe(
                bk_show,
                use_container_width=True,
                height=460,
                hide_index=True,
                column_config={"Valor": _val_cfg, "E/S": _es_cfg},
                selection_mode="multi-row",
                on_select="rerun",
                key=bk_key,
            )

        sp_sel_rows = sel_sp.selection.rows if hasattr(sel_sp, "selection") else []
        bk_sel_rows = sel_bk.selection.rows if hasattr(sel_bk, "selection") else []
        n_sp = len(sp_sel_rows)
        n_bk = len(bk_sel_rows)

        with col_mid:
            st.caption("**Ações**")
            st.markdown("---")

            if n_sp > 0 and n_bk > 0:
                # ── N Sponte → 1 Banco  ou  1 Sponte → N Banco ────────────────
                sp_selecionados = [sp_filtrado.iloc[i] for i in sp_sel_rows]
                bk_selecionados = [bk_filtrado.iloc[i] for i in bk_sel_rows]
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

                    if diff > 0.02:
                        st.warning(f"⚠️ Dif: {_md_val(diff)}")

                    if n_sp > 1:
                        lbl = f"🔗 Vincular {n_sp}→1"
                    elif n_bk > 1:
                        lbl = f"🔗 Vincular 1→{n_bk}"
                    else:
                        lbl = "🔗 Vincular"
                    if st.button(lbl, type="primary", use_container_width=True):
                        if n_bk == 1:
                            # N:1 — vários Sponte → 1 Banco
                            bk_r = bk_selecionados[0]
                            for r in sp_selecionados:
                                db.salvar_conciliacao(mes, ano, "manual",
                                                      sponte_chave=r["chave"],
                                                      banco_chave=bk_r["chave"])
                        else:
                            # 1:N — 1 Sponte → vários Banco
                            # Salva UM ÚNICO registro com banco_chaves separadas por §§
                            # para não duplicar o sponte_chave e não quebrar o auto-match
                            sp_r = sp_selecionados[0]
                            bk_chaves_unidas = "§§".join(r["chave"] for r in bk_selecionados)
                            db.salvar_conciliacao(mes, ano, "manual",
                                                  sponte_chave=sp_r["chave"],
                                                  banco_chave=bk_chaves_unidas)
                        st.session_state["conc_cnt"] += 1
                        st.rerun()

            elif n_sp > 0:
                # ── Só Sponte selecionado ─────────────────────────────────────
                sp_selecionados = [sp_filtrado.iloc[i] for i in sp_sel_rows]
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
                    sp_r = sp_filtrado.iloc[sp_sel_rows[0]]
                    st.caption("*Selecione Banco(s) para vincular, ou ignore:*")
                    with st.form(key=f"form_isp_{cnt}"):
                        just = st.text_input("Motivo:", placeholder="ex: saída em caixa físico")
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
                    bk_r = bk_filtrado.iloc[bk_sel_rows[0]]
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
with aba_conc:
    if n_auto == 0 and n_manual == 0 and n_ign == 0:
        st.info("Nenhum item conciliado ainda.")

    # ── Automáticos ───────────────────────────────────────────────────────────
    if n_auto > 0:
        st.caption(f"🤖 **{n_auto} conciliados automaticamente** — selecione linhas e clique em Desvincular para corrigir")
        auto_rows = []
        auto_pairs = []   # (sp_df_index, bk_df_index) para cada linha da tabela
        for chave, n in sorted(chaves_auto_counts.items()):
            sp_matches = sponte_df[sponte_df["chave"] == chave].iloc[:n]
            bk_matches = banco_df[banco_df["chave"] == chave].iloc[:n]
            for i in range(n):
                sp_r = sp_matches.iloc[i]
                bk_r = bk_matches.iloc[i]
                auto_rows.append({
                    "E/S": sp_r["es"],
                    "Sponte": f"{pd.to_datetime(sp_r['data']).strftime('%d/%m')} | {str(sp_r['categoria'])[:28]} | {fmt_br(abs(sp_r['valor']))}",
                    "Banco":  f"{bk_r['data_fmt'][:5]} | {str(bk_r['historico'])[:28]} | {fmt_br(abs(float(bk_r['valor'])))}",
                })
                auto_pairs.append((sp_r.name, bk_r.name))

        sel_auto = st.dataframe(
            pd.DataFrame(auto_rows),
            use_container_width=True,
            hide_index=True,
            height=min(400, 38 + 35 * n_auto),
            selection_mode="multi-row",
            on_select="rerun",
            key=f"sel_auto_{mes}_{ano}",
        )
        sel_auto_rows = sel_auto.selection.rows if hasattr(sel_auto, "selection") else []
        if sel_auto_rows:
            st.warning(f"**{len(sel_auto_rows)} item(s) selecionado(s)** — confirme para desvincular e mover para Pendentes.")
            if st.button("🔓 Desvincular selecionados", type="primary"):
                for idx in sel_auto_rows:
                    sp_dfidx, bk_dfidx = auto_pairs[idx]
                    sp_r = sponte_df.loc[sp_dfidx]
                    bk_r = banco_df.loc[bk_dfidx]
                    db.salvar_conciliacao(mes, ano, "desvincular",
                                         sponte_chave=sp_r["chave"],
                                         banco_chave=bk_r["chave"])
                st.rerun()

    # ── Manuais ───────────────────────────────────────────────────────────────
    if n_manual > 0:
        st.caption(f"🔗 **{n_manual} vinculados manualmente**")
        manual_df = conc_df[conc_df["tipo"] == "manual"].copy()
        shown_ids: set = set()

        def _sp_txt(chave):
            r = sponte_df[sponte_df["chave"] == chave]
            return (f"{pd.to_datetime(r.iloc[0]['data']).strftime('%d/%m')} | "
                    f"{str(r.iloc[0]['categoria'])[:25]} | {fmt_br(abs(r.iloc[0]['valor']))}"
                    if not r.empty else str(chave))

        def _bk_txt(chave):
            r = banco_df[banco_df["chave"] == chave]
            return (f"{r.iloc[0]['data_fmt'][:5]} | "
                    f"{str(r.iloc[0]['historico'])[:25]} | {fmt_br(abs(float(r.iloc[0]['valor'])))}"
                    if not r.empty else str(chave))

        # ── N:1 — vários Sponte → 1 Banco ────────────────────────────────────
        bk_counts = manual_df["banco_chave"].value_counts()
        for bk_chave in bk_counts[bk_counts > 1].index:
            grupo = manual_df[manual_df["banco_chave"] == bk_chave]
            ids_grupo = grupo["id"].tolist()
            shown_ids.update(ids_grupo)
            ca, cb, cc = st.columns([5, 5, 1])
            with ca:
                for _, c in grupo.iterrows():
                    st.write(f"🔵 {_sp_txt(c['sponte_chave'])}")
            cb.write(f"🏦 {_bk_txt(bk_chave)}")
            if cc.button("✖", key=f"del_n1_{ids_grupo[0]}", help="Desvincular grupo"):
                for id_c in ids_grupo:
                    db.deletar_conciliacao(int(id_c))
                st.rerun()

        # ── 1:N — novo formato: 1 registro com banco_chaves separadas por §§ ──
        restante = manual_df[~manual_df["id"].isin(shown_ids)]
        for _, c in restante.iterrows():
            bk_raw = str(c.get("banco_chave", ""))
            if "§§" not in bk_raw:
                continue
            shown_ids.add(c["id"])
            bk_lista = [ch.strip() for ch in bk_raw.split("§§") if ch.strip()]
            ca, cb, cc = st.columns([5, 5, 1])
            ca.write(f"🔵 {_sp_txt(c['sponte_chave'])}")
            with cb:
                for bk_ch in bk_lista:
                    st.write(f"🏦 {_bk_txt(bk_ch)}")
            if cc.button("✖", key=f"del_1n_new_{c['id']}", help="Desvincular"):
                db.deletar_conciliacao(int(c["id"]))
                st.rerun()

        # ── 1:N — formato antigo: vários registros com mesmo sponte_chave ────
        restante = manual_df[~manual_df["id"].isin(shown_ids)]
        sp_counts = restante["sponte_chave"].value_counts()
        for sp_chave in sp_counts[sp_counts > 1].index:
            grupo = restante[restante["sponte_chave"] == sp_chave]
            ids_grupo = grupo["id"].tolist()
            shown_ids.update(ids_grupo)
            ca, cb, cc = st.columns([5, 5, 1])
            ca.write(f"🔵 {_sp_txt(sp_chave)}")
            with cb:
                for _, c in grupo.iterrows():
                    st.write(f"🏦 {_bk_txt(c['banco_chave'])}")
            if cc.button("✖", key=f"del_1n_{ids_grupo[0]}", help="Desvincular grupo"):
                for id_c in ids_grupo:
                    db.deletar_conciliacao(int(id_c))
                st.rerun()

        # ── 1:1 ───────────────────────────────────────────────────────────────
        for _, c in manual_df[~manual_df["id"].isin(shown_ids)].iterrows():
            ca, cb, cc = st.columns([5, 5, 1])
            ca.write(f"🔵 {_sp_txt(c['sponte_chave'])}")
            cb.write(f"🏦 {_bk_txt(c['banco_chave'])}")
            if cc.button("✖", key=f"del_11_{c['id']}", help="Desvincular"):
                db.deletar_conciliacao(int(c["id"]))
                st.rerun()

    # ── Ignorados ─────────────────────────────────────────────────────────────
    if n_ign > 0:
        st.caption(f"🙈 **{n_ign} ignorados**")
        ign_df = conc_df[conc_df["tipo"].str.startswith("ignorado", na=False)]
        for _, c in ign_df.iterrows():
            just = f" — *{c['justificativa']}*" if c.get("justificativa") else ""
            if c["tipo"] == "ignorado_sponte" and pd.notna(c.get("sponte_chave")):
                sp_rows = sponte_df[sponte_df["chave"] == c["sponte_chave"]]
                texto = (f"Sponte — {pd.to_datetime(sp_rows.iloc[0]['data']).strftime('%d/%m')} | {str(sp_rows.iloc[0]['categoria'])[:25]} | {fmt_br(abs(sp_rows.iloc[0]['valor']))}"
                         if not sp_rows.empty else f"Sponte — {c['sponte_chave']}")
            else:
                bk_rows = banco_df[banco_df["chave"] == c.get("banco_chave", "")]
                texto = (f"Banco — {bk_rows.iloc[0]['data_fmt'][:5]} | {str(bk_rows.iloc[0]['historico'])[:25]} | {fmt_br(abs(float(bk_rows.iloc[0]['valor'])))}"
                         if not bk_rows.empty else f"Banco — {c.get('banco_chave', '')}")
            ca, cb = st.columns([11, 1])
            ca.write(f"🙈 {texto}{just}")
            if cb.button("✖", key=f"del_i_{c['id']}", help="Remover"):
                db.deletar_conciliacao(int(c["id"]))
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
