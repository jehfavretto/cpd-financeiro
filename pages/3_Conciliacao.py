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
    """Converte YYYYMMDD → DD/MM/YYYY para exibição."""
    try:
        d = datetime.strptime(str(data_mov), "%Y%m%d")
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    except Exception:
        return str(data_mov)


def make_key_sponte(row) -> str:
    d = row["data"]
    data_str = f"{d.day:02d}/{d.month:02d}/{d.year}"
    return f"{data_str}|{row['es']}|{row['valor']:.2f}".replace(".", ",")


def make_key_banco(row) -> str:
    data_str = _data_banco_fmt(row["data_mov"])
    es = "E" if row["deb_cred"] == "C" else "S"
    return f"{data_str}|{es}|{abs(float(row['valor'])):.2f}".replace(".", ",")


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

chaves_sp_usadas = set(conc_df["sponte_chave"].dropna())
chaves_bk_usadas = set(conc_df["banco_chave"].dropna())

# ── Auto-match: chave idêntica nos dois sistemas, ainda não processada ─────────
chaves_auto = (
    (set(banco_df["chave"]) & set(sponte_df["chave"]))
    - chaves_sp_usadas
    - chaves_bk_usadas
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

with st.expander(
    f"✅ Conciliados — {n_auto} automáticos | {n_manual} manuais | {n_ign} ignorados",
    expanded=False,
):

    # ── Auto-matches ───────────────────────────────────────────────────────────
    if n_auto > 0:
        st.caption("🤖 **Conciliados automaticamente** (mesma data, tipo e valor)")
        auto_rows = []
        for chave in sorted(chaves_auto):
            sp_r = sponte_df[sponte_df["chave"] == chave].iloc[0]
            bk_r = banco_df[banco_df["chave"] == chave].iloc[0]
            auto_rows.append({
                "Sponte": f"{sp_r['data']} | {str(sp_r['categoria'])[:35]} | R$ {sp_r['valor']:,.2f}",
                "Banco":  f"{bk_r['data_fmt']} | {str(bk_r['historico'])[:35]} | R$ {abs(float(bk_r['valor'])):,.2f}",
            })
        st.dataframe(
            pd.DataFrame(auto_rows),
            use_container_width=True,
            hide_index=True,
            height=min(220, 38 + 35 * n_auto),
        )

    # ── Vínculos manuais ───────────────────────────────────────────────────────
    if n_manual > 0:
        st.caption("🔗 **Vinculados manualmente**")
        manual_df = conc_df[conc_df["tipo"] == "manual"]
        for _, c in manual_df.iterrows():
            sp_rows = sponte_df[sponte_df["chave"] == c["sponte_chave"]]
            bk_rows = banco_df[banco_df["chave"] == c["banco_chave"]]
            sp_text = (
                f"{sp_rows.iloc[0]['data']} | {str(sp_rows.iloc[0]['categoria'])[:25]} | R$ {sp_rows.iloc[0]['valor']:,.2f}"
                if not sp_rows.empty else c["sponte_chave"]
            )
            bk_text = (
                f"{bk_rows.iloc[0]['data_fmt']} | {str(bk_rows.iloc[0]['historico'])[:25]} | R$ {abs(float(bk_rows.iloc[0]['valor'])):,.2f}"
                if not bk_rows.empty else c["banco_chave"]
            )
            ca, cb, cc = st.columns([5, 5, 1])
            ca.write(f"🔵 {sp_text}")
            cb.write(f"🏦 {bk_text}")
            if cc.button("✖", key=f"del_m_{c['id']}", help="Desvincular"):
                db.deletar_conciliacao(int(c["id"]))
                st.rerun()

    # ── Ignorados ──────────────────────────────────────────────────────────────
    if n_ign > 0:
        st.caption("🙈 **Ignorados**")
        ign_df = conc_df[conc_df["tipo"].str.startswith("ignorado", na=False)]
        for _, c in ign_df.iterrows():
            just = f" — *{c['justificativa']}*" if c.get("justificativa") else ""
            if c["tipo"] == "ignorado_sponte" and pd.notna(c.get("sponte_chave")):
                sp_rows = sponte_df[sponte_df["chave"] == c["sponte_chave"]]
                if not sp_rows.empty:
                    r = sp_rows.iloc[0]
                    texto = f"Sponte — {r['data']} | {str(r['categoria'])[:25]} | R$ {r['valor']:,.2f}"
                else:
                    texto = f"Sponte — {c['sponte_chave']}"
            else:
                bk_rows = banco_df[banco_df["chave"] == c.get("banco_chave", "")]
                if not bk_rows.empty:
                    r = bk_rows.iloc[0]
                    texto = f"Banco — {r['data_fmt']} | {str(r['historico'])[:25]} | R$ {abs(float(r['valor'])):,.2f}"
                else:
                    texto = f"Banco — {c.get('banco_chave', '')}"
            ca, cb = st.columns([11, 1])
            ca.write(f"🙈 {texto}{just}")
            if cb.button("✖", key=f"del_i_{c['id']}", help="Remover"):
                db.deletar_conciliacao(int(c["id"]))
                st.rerun()

    if n_auto == 0 and n_manual == 0 and n_ign == 0:
        st.info("Nenhum item conciliado ainda.")

st.divider()

# ── A Conciliar ────────────────────────────────────────────────────────────────
if sponte_pendente.empty and banco_pendente.empty:
    st.success("🎉 **Conciliação completa!** Todos os lançamentos foram conciliados.")
    st.stop()

st.subheader("⏳ A Conciliar")
st.caption(
    "Selecione **uma linha** do Sponte e **uma linha** do Banco para vincular, "
    "ou apenas **um lado** para ignorar com justificativa."
)

# Contador de ações — incrementar após cada ação reseta as seleções dos dataframes
if "conc_cnt" not in st.session_state:
    st.session_state["conc_cnt"] = 0
cnt    = st.session_state["conc_cnt"]
sp_key = f"dfsp_{mes}_{ano}_{cnt}"
bk_key = f"dfbk_{mes}_{ano}_{cnt}"

# ── Layout side-by-side ────────────────────────────────────────────────────────
col_sp, col_mid, col_bk = st.columns([5, 2, 5])

sp_show = pd.DataFrame({
    "Data":      sponte_pendente["data"].astype(str),
    "Categoria": sponte_pendente["categoria"].str[:32],
    "E/S":       sponte_pendente["es"],
    "Valor":     sponte_pendente["valor"].map(lambda v: f"R$ {v:,.2f}"),
})

bk_show = pd.DataFrame({
    "Data":      banco_pendente["data_fmt"],
    "Histórico": banco_pendente["historico"].str[:32],
    "D/C":       banco_pendente["deb_cred"],
    "Valor":     banco_pendente["valor"].map(lambda v: f"R$ {abs(float(v)):,.2f}"),
})

with col_sp:
    st.markdown("**📋 FluxoCaixa Sponte**")
    sel_sp = st.dataframe(
        sp_show,
        use_container_width=True,
        height=460,
        hide_index=False,
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
        hide_index=False,
        selection_mode="single-row",
        on_select="rerun",
        key=bk_key,
    )

# ── Painel de ações ────────────────────────────────────────────────────────────
sp_sel_rows = sel_sp.selection.rows if hasattr(sel_sp, "selection") else []
bk_sel_rows = sel_bk.selection.rows if hasattr(sel_bk, "selection") else []
sp_idx = sp_sel_rows[0] if sp_sel_rows else None
bk_idx = bk_sel_rows[0] if bk_sel_rows else None

with col_mid:
    st.markdown("**Ações**")
    st.markdown("---")

    # ── Dois itens selecionados: Vincular ──────────────────────────────────────
    if sp_idx is not None and bk_idx is not None:
        sp_r = sponte_pendente.iloc[sp_idx]
        bk_r = banco_pendente.iloc[bk_idx]
        st.success(
            f"**Sponte #{sp_idx + 1}**  \n"
            f"{str(sp_r['categoria'])[:22]}  \n"
            f"R$ {sp_r['valor']:,.2f}"
        )
        st.info(
            f"**Banco #{bk_idx + 1}**  \n"
            f"{str(bk_r['historico'])[:22]}  \n"
            f"R$ {abs(float(bk_r['valor'])):,.2f}"
        )
        if st.button("🔗 Vincular", type="primary", use_container_width=True):
            db.salvar_conciliacao(
                mes, ano, "manual",
                sponte_chave=sp_r["chave"],
                banco_chave=bk_r["chave"],
            )
            st.session_state["conc_cnt"] += 1
            st.rerun()

    # ── Apenas Sponte selecionado: Ignorar ────────────────────────────────────
    elif sp_idx is not None:
        sp_r = sponte_pendente.iloc[sp_idx]
        st.info(
            f"**Sponte #{sp_idx + 1}**  \n"
            f"{str(sp_r['categoria'])[:22]}  \n"
            f"R$ {sp_r['valor']:,.2f}"
        )
        with st.form(key=f"form_isp_{cnt}"):
            just = st.text_input("Motivo:", placeholder="ex: saída em caixa físico")
            if st.form_submit_button("🙈 Ignorar Sponte", use_container_width=True):
                db.salvar_conciliacao(
                    mes, ano, "ignorado_sponte",
                    sponte_chave=sp_r["chave"],
                    justificativa=just or None,
                )
                st.session_state["conc_cnt"] += 1
                st.rerun()

    # ── Apenas Banco selecionado: Ignorar ─────────────────────────────────────
    elif bk_idx is not None:
        bk_r = banco_pendente.iloc[bk_idx]
        st.info(
            f"**Banco #{bk_idx + 1}**  \n"
            f"{str(bk_r['historico'])[:22]}  \n"
            f"R$ {abs(float(bk_r['valor'])):,.2f}"
        )
        with st.form(key=f"form_ibk_{cnt}"):
            just = st.text_input("Motivo:", placeholder="ex: tarifa bancária")
            if st.form_submit_button("🙈 Ignorar Banco", use_container_width=True):
                db.salvar_conciliacao(
                    mes, ano, "ignorado_banco",
                    banco_chave=bk_r["chave"],
                    justificativa=just or None,
                )
                st.session_state["conc_cnt"] += 1
                st.rerun()

    # ── Nada selecionado ───────────────────────────────────────────────────────
    else:
        st.markdown(
            "👈 Clique em uma linha do **Sponte** e uma do **Banco** para vincular.  \n\n"
            "Ou clique em um item de apenas um lado para ignorar."
        )
