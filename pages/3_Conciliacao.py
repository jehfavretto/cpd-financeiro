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
chaves_bk_desvincular = set(_desv["banco_chave"].dropna())  if not _desv.empty else set()
chaves_sp_usadas      = set(_conc_sem_desv["sponte_chave"].dropna()) if not _conc_sem_desv.empty else set()
chaves_bk_usadas      = set(_conc_sem_desv["banco_chave"].dropna())  if not _conc_sem_desv.empty else set()

# ── Auto-match: chave idêntica nos dois sistemas, ainda não processada ─────────
chaves_auto = (
    (set(banco_df["chave"]) & set(sponte_df["chave"]))
    - chaves_sp_usadas
    - chaves_bk_usadas
    - chaves_sp_desvincular   # bloqueados pelo usuário — voltam para pendentes
)

# ── Separa pendentes ───────────────────────────────────────────────────────────
mask_sp_ok = sponte_df["chave"].isin(chaves_auto) | sponte_df["chave"].isin(chaves_sp_usadas)
mask_bk_ok = banco_df["chave"].isin(chaves_auto)  | banco_df["chave"].isin(chaves_bk_usadas)
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
n_auto   = len(chaves_auto)
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
            "Selecione **uma linha** do Sponte e **uma linha** do Banco para vincular, "
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

        sp_show = pd.DataFrame({
            "Data":      pd.to_datetime(sp_filtrado["data"]).dt.strftime("%d/%m"),
            "Categoria": sp_filtrado["categoria"].str[:22],
            "E/S":       sp_filtrado["es"],
            "Valor":     sp_filtrado["valor"].map(lambda v: fmt_br(abs(v))),
        })

        bk_show = pd.DataFrame({
            "Data":      bk_filtrado["data_fmt"].str[:5],
            "Histórico": bk_filtrado["historico"].str[:22],
            "E/S":       bk_filtrado["deb_cred"],
            "Valor":     bk_filtrado["valor"].map(lambda v: fmt_br(abs(float(v)))),
        })

        with col_sp:
            st.markdown("**📋 FluxoCaixa Sponte**")
            sel_sp = st.dataframe(
                sp_show,
                use_container_width=True,
                height=460,
                hide_index=True,
                selection_mode="single-row",
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
                selection_mode="single-row",
                on_select="rerun",
                key=bk_key,
            )

        sp_sel_rows = sel_sp.selection.rows if hasattr(sel_sp, "selection") else []
        bk_sel_rows = sel_bk.selection.rows if hasattr(sel_bk, "selection") else []
        sp_idx = sp_sel_rows[0] if sp_sel_rows else None
        bk_idx = bk_sel_rows[0] if bk_sel_rows else None

        with col_mid:
            st.markdown("**Ações**")
            st.markdown("---")

            if sp_idx is not None and bk_idx is not None:
                sp_r = sp_filtrado.iloc[sp_idx]
                bk_r = bk_filtrado.iloc[bk_idx]
                st.success(
                    f"**Sponte**  \n{str(sp_r['categoria'])[:22]}  \n"
                    f"{fmt_br(abs(sp_r['valor']))}"
                )
                st.info(
                    f"**Banco**  \n{str(bk_r['historico'])[:22]}  \n"
                    f"{fmt_br(abs(float(bk_r['valor'])))}"
                )
                if st.button("🔗 Vincular", type="primary", use_container_width=True):
                    db.salvar_conciliacao(mes, ano, "manual",
                                          sponte_chave=sp_r["chave"],
                                          banco_chave=bk_r["chave"])
                    st.session_state["conc_cnt"] += 1
                    st.rerun()

            elif sp_idx is not None:
                sp_r = sp_filtrado.iloc[sp_idx]
                st.info(f"**Sponte**  \n{str(sp_r['categoria'])[:22]}  \n{fmt_br(abs(sp_r['valor']))}")
                with st.form(key=f"form_isp_{cnt}"):
                    just = st.text_input("Motivo:", placeholder="ex: saída em caixa físico")
                    if st.form_submit_button("🙈 Ignorar Sponte", use_container_width=True):
                        db.salvar_conciliacao(mes, ano, "ignorado_sponte",
                                              sponte_chave=sp_r["chave"],
                                              justificativa=just or None)
                        st.session_state["conc_cnt"] += 1
                        st.rerun()

            elif bk_idx is not None:
                bk_r = bk_filtrado.iloc[bk_idx]
                st.info(f"**Banco**  \n{str(bk_r['historico'])[:22]}  \n{fmt_br(abs(float(bk_r['valor'])))}")
                with st.form(key=f"form_ibk_{cnt}"):
                    just = st.text_input("Motivo:", placeholder="ex: tarifa bancária")
                    if st.form_submit_button("🙈 Ignorar Banco", use_container_width=True):
                        db.salvar_conciliacao(mes, ano, "ignorado_banco",
                                              banco_chave=bk_r["chave"],
                                              justificativa=just or None)
                        st.session_state["conc_cnt"] += 1
                        st.rerun()

            else:
                st.markdown(
                    "👈 Selecione uma linha do **Sponte** e uma do **Banco** para vincular.  \n\n"
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
        auto_chaves = []
        for chave in sorted(chaves_auto):
            sp_r = sponte_df[sponte_df["chave"] == chave].iloc[0]
            bk_r = banco_df[banco_df["chave"] == chave].iloc[0]
            auto_rows.append({
                "E/S": sp_r["es"],
                "Sponte": f"{pd.to_datetime(sp_r['data']).strftime('%d/%m')} | {str(sp_r['categoria'])[:28]} | {fmt_br(abs(sp_r['valor']))}",
                "Banco":  f"{bk_r['data_fmt'][:5]} | {str(bk_r['historico'])[:28]} | {fmt_br(abs(float(bk_r['valor'])))}",
            })
            auto_chaves.append(chave)

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
                    chave = auto_chaves[idx]
                    sp_r  = sponte_df[sponte_df["chave"] == chave].iloc[0]
                    bk_r  = banco_df[banco_df["chave"] == chave].iloc[0]
                    db.salvar_conciliacao(mes, ano, "desvincular",
                                         sponte_chave=sp_r["chave"],
                                         banco_chave=bk_r["chave"])
                st.rerun()

    # ── Manuais ───────────────────────────────────────────────────────────────
    if n_manual > 0:
        st.caption(f"🔗 **{n_manual} vinculados manualmente**")
        manual_df = conc_df[conc_df["tipo"] == "manual"]
        for _, c in manual_df.iterrows():
            sp_rows = sponte_df[sponte_df["chave"] == c["sponte_chave"]]
            bk_rows = banco_df[banco_df["chave"] == c["banco_chave"]]
            sp_text = (f"{pd.to_datetime(sp_rows.iloc[0]['data']).strftime('%d/%m')} | {str(sp_rows.iloc[0]['categoria'])[:25]} | {fmt_br(abs(sp_rows.iloc[0]['valor']))}"
                       if not sp_rows.empty else c["sponte_chave"])
            bk_text = (f"{bk_rows.iloc[0]['data_fmt'][:5]} | {str(bk_rows.iloc[0]['historico'])[:25]} | {fmt_br(abs(float(bk_rows.iloc[0]['valor'])))}"
                       if not bk_rows.empty else c["banco_chave"])
            ca, cb, cc = st.columns([5, 5, 1])
            ca.write(f"🔵 {sp_text}")
            cb.write(f"🏦 {bk_text}")
            if cc.button("✖", key=f"del_m_{c['id']}", help="Desvincular"):
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
