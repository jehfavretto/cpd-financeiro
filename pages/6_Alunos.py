"""
Página de gestão de alunos e responsáveis.
Permite visualizar, editar, adicionar e importar alunos por ano letivo.
"""
from __future__ import annotations
import re
import streamlit as st
import pandas as pd
import db.client as db

# ── Ordem definida das turmas ─────────────────────────────────────────────────
ORDEM_TURMAS = [
    "Berçário", "Maternal",
    "I período", "II Período", "III Período", "Pré",
    "1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano",
]

def _sort_turma(t: str) -> int:
    """Retorna índice para ordenar turma; desconhecidas vão para o final."""
    try:
        return ORDEM_TURMAS.index(t)
    except ValueError:
        return 999


# ── Limpeza para import de Excel ──────────────────────────────────────────────
def _limpar_responsavel(s: str) -> str:
    s = str(s).strip()
    # Remove CPF/CNPJ do início: ex "38.360.955 FULANO" → "FULANO"
    s = re.sub(r'^\d[\d\.\-]{0,13}\s+', '', s)
    return s.strip()


def _parse_turma(t: str):
    """Retorna (nome_turma, ano) a partir de 'I período - 2026' etc."""
    t = str(t).strip()
    m = re.search(r'(\d{4})', t)
    ano = int(m.group(1)) if m else None
    nome = re.sub(r'\s*[-–]\s*\d{4}\s*', '', t).strip()
    nome = re.sub(r'\s+', ' ', nome)
    return nome, ano


# ── Página ────────────────────────────────────────────────────────────────────
st.title("👨‍🎓 Alunos e Responsáveis")

# ── Seleção de ano ────────────────────────────────────────────────────────────
anos_existentes = db.anos_com_alunos()
ano_atual = 2026  # fallback

col_ano, col_novo, _ = st.columns([2, 2, 6])
with col_ano:
    if anos_existentes:
        ano_sel = st.selectbox("Ano letivo", anos_existentes, index=0)
    else:
        ano_sel = st.number_input("Ano letivo", value=ano_atual, step=1, format="%d")

# ── Carregar dados ────────────────────────────────────────────────────────────
df = db.carregar_alunos(int(ano_sel))

# ── Métricas rápidas ──────────────────────────────────────────────────────────
if not df.empty:
    n_alunos     = df["nome_aluno"].nunique()
    n_resp       = df["nome_responsavel"].nunique()
    n_turmas     = df["turma"].nunique()
    m1, m2, m3 = st.columns(3)
    m1.metric("👦 Alunos únicos", n_alunos)
    m2.metric("👪 Responsáveis únicos", n_resp)
    m3.metric("🏫 Turmas", n_turmas)
    st.divider()

# ── Abas ──────────────────────────────────────────────────────────────────────
aba_tabela, aba_add, aba_import = st.tabs(["📋 Tabela", "➕ Novo registro", "📥 Importar Excel"])

# ── ABA 1 — Tabela editável ───────────────────────────────────────────────────
with aba_tabela:
    if df.empty:
        st.info("Nenhum aluno cadastrado para este ano. Use a aba **Importar Excel** para começar.")
    else:
        # Filtros
        fc1, fc2 = st.columns([4, 3])
        busca = fc1.text_input("🔍 Pesquisar", placeholder="aluno, responsável…", key=f"busca_alunos_{ano_sel}")
        turmas_disp = sorted(df["turma"].unique().tolist(), key=_sort_turma)
        turma_sel = fc2.multiselect("Turma", turmas_disp, key=f"turma_sel_{ano_sel}", placeholder="Todas as turmas")

        df_show = df.copy()
        if busca.strip():
            q = busca.strip().lower()
            df_show = df_show[
                df_show["nome_aluno"].str.lower().str.contains(q, na=False) |
                df_show["nome_responsavel"].str.lower().str.contains(q, na=False)
            ]
        if turma_sel:
            df_show = df_show[df_show["turma"].isin(turma_sel)]

        st.caption(f"{len(df_show)} registro(s) exibido(s)")

        # Tabela com seleção para deletar
        sel = st.dataframe(
            df_show[["turma", "nome_aluno", "nome_responsavel"]],
            use_container_width=True,
            hide_index=True,
            height=min(600, 40 + 35 * len(df_show)),
            selection_mode="multi-row",
            on_select="rerun",
            key=f"df_alunos_{ano_sel}",
            column_config={
                "turma":            st.column_config.TextColumn("Turma",         width="medium"),
                "nome_aluno":       st.column_config.TextColumn("Aluno",         width="large"),
                "nome_responsavel": st.column_config.TextColumn("Responsável",   width="large"),
            },
        )

        sel_rows = sel.selection.rows if hasattr(sel, "selection") else []
        if sel_rows:
            st.warning(f"⚠️ {len(sel_rows)} linha(s) selecionada(s) para exclusão")
            if st.button(f"🗑️ Excluir {len(sel_rows)} registro(s)", type="primary", key="btn_del_alunos"):
                ids_para_deletar = df_show.iloc[sel_rows]["id"].tolist()
                for rid in ids_para_deletar:
                    db.deletar_aluno(int(rid))
                st.success("Registros excluídos.")
                st.rerun()

        # ── Editar registro selecionado (apenas se 1 linha) ───────────────────
        if len(sel_rows) == 1:
            st.divider()
            st.markdown("**✏️ Editar registro selecionado**")
            row_edit = df_show.iloc[sel_rows[0]]
            with st.form("form_editar_aluno"):
                e1, e2, e3 = st.columns(3)
                turma_edit = e1.selectbox(
                    "Turma", ORDEM_TURMAS,
                    index=_sort_turma(row_edit["turma"]) if row_edit["turma"] in ORDEM_TURMAS else 0,
                    key="edit_turma",
                )
                aluno_edit = e2.text_input("Aluno", value=row_edit["nome_aluno"], key="edit_aluno")
                resp_edit  = e3.text_input("Responsável", value=row_edit["nome_responsavel"], key="edit_resp")
                if st.form_submit_button("💾 Salvar alteração", type="primary"):
                    db.upsert_aluno(
                        ano=int(ano_sel),
                        turma=turma_edit,
                        nome_aluno=aluno_edit,
                        nome_responsavel=resp_edit,
                        id=int(row_edit["id"]),
                    )
                    st.success("Registro atualizado!")
                    st.rerun()

        # ── Resumo por turma ──────────────────────────────────────────────────
        st.divider()
        st.markdown("**📊 Alunos por turma**")
        resumo = (
            df.groupby("turma")["nome_aluno"]
            .nunique()
            .reset_index()
            .rename(columns={"nome_aluno": "alunos"})
        )
        resumo = resumo.sort_values("turma", key=lambda s: s.map(_sort_turma))
        st.dataframe(
            resumo,
            use_container_width=False,
            hide_index=True,
            column_config={
                "turma":  st.column_config.TextColumn("Turma",   width="medium"),
                "alunos": st.column_config.NumberColumn("Alunos", width="small"),
            },
        )


# ── ABA 2 — Adicionar novo registro ──────────────────────────────────────────
with aba_add:
    st.markdown("Adicione um aluno ou responsável avulso.")
    with st.form("form_novo_aluno"):
        a1, a2, a3 = st.columns(3)
        nova_turma = a1.selectbox("Turma", ORDEM_TURMAS, key="add_turma")
        novo_aluno = a2.text_input("Nome do aluno", key="add_aluno")
        novo_resp  = a3.text_input("Nome do responsável", key="add_resp")
        if st.form_submit_button("➕ Adicionar", type="primary"):
            if not novo_aluno.strip() or not novo_resp.strip():
                st.error("Preencha nome do aluno e do responsável.")
            else:
                db.upsert_aluno(
                    ano=int(ano_sel),
                    turma=nova_turma,
                    nome_aluno=novo_aluno.strip(),
                    nome_responsavel=novo_resp.strip(),
                )
                st.success(f"✅ {novo_aluno} adicionado!")
                st.rerun()


# ── ABA 3 — Importar Excel ────────────────────────────────────────────────────
with aba_import:
    st.markdown(
        "Faça upload de uma planilha com colunas **Turma**, **Nome da criança** e "
        "**Remetente/Destinatario**. O formato deve ser igual ao exportado do Sponte."
    )

    SKIP_TURMAS = {"COLÔNIA 2026", "Caiu na conta da Maria CPF"}

    uploaded = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx", "xls"], key="upload_alunos")

    if uploaded:
        try:
            df_raw = pd.read_excel(uploaded)
            # Validar colunas mínimas
            cols_obrig = {"Turma", "Nome da criança", "Remetente/Destinatario"}
            if not cols_obrig.issubset(set(df_raw.columns)):
                st.error(f"O arquivo precisa ter as colunas: {', '.join(cols_obrig)}")
            else:
                # Processar
                df_raw = df_raw[~df_raw["Turma"].isin(SKIP_TURMAS)].dropna(subset=["Turma", "Nome da criança", "Remetente/Destinatario"]).copy()
                df_raw["nome_responsavel"] = df_raw["Remetente/Destinatario"].apply(_limpar_responsavel)
                parsed = df_raw["Turma"].apply(_parse_turma)
                df_raw["turma"] = [p[0] for p in parsed]
                df_raw["ano"]   = [p[1] for p in parsed]
                df_raw["nome_aluno"] = df_raw["Nome da criança"].str.strip()

                # Deduplica
                df_proc = df_raw[["ano", "turma", "nome_aluno", "nome_responsavel"]].drop_duplicates()

                # Filtra só as do ano selecionado (ou todos se não mapeado)
                df_proc = df_proc[df_proc["ano"] == int(ano_sel)]

                if df_proc.empty:
                    st.warning(f"Nenhum registro para o ano {ano_sel} encontrado no arquivo.")
                else:
                    st.success(f"**{len(df_proc)} registros** encontrados para {ano_sel}.")
                    st.dataframe(
                        df_proc[["turma", "nome_aluno", "nome_responsavel"]].sort_values(["turma", "nome_aluno"]),
                        use_container_width=True,
                        hide_index=True,
                    )

                    modo = st.radio(
                        "Como importar?",
                        ["Adicionar aos existentes", "Substituir todos os registros do ano"],
                        key="modo_import",
                    )
                    st.caption(
                        "⚠️ **Substituir** apaga TODOS os registros do ano antes de importar."
                        if modo == "Substituir todos os registros do ano"
                        else "**Adicionar** insere os novos sem remover os existentes."
                    )

                    if st.button("📥 Confirmar importação", type="primary", key="btn_confirmar_import"):
                        if modo == "Substituir todos os registros do ano":
                            db.limpar_alunos_ano(int(ano_sel))
                        rows = [
                            {
                                "ano":              int(r["ano"]),
                                "turma":            r["turma"],
                                "nome_aluno":       r["nome_aluno"],
                                "nome_responsavel": r["nome_responsavel"],
                            }
                            for _, r in df_proc.iterrows()
                        ]
                        db.salvar_alunos_lote(rows)
                        st.success(f"✅ {len(rows)} registros importados com sucesso!")
                        st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
