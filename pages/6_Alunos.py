"""
Página de gestão de alunos e responsáveis.
Um aluno pode ter vários responsáveis — exibidos em uma só linha.
"""
from __future__ import annotations
import re
import streamlit as st
import pandas as pd
import db.client as db

# ── Ordem das turmas ──────────────────────────────────────────────────────────
ORDEM_TURMAS = [
    "Berçário", "Maternal",
    "I período", "II Período", "III Período", "Pré",
    "1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano",
]

def _sort_turma(t: str) -> int:
    try:
        return ORDEM_TURMAS.index(t)
    except ValueError:
        return 999


# ── Padronização de nomes (Title Case BR) ─────────────────────────────────────
_MINUSC = {"de","da","do","dos","das","e","em","na","no","nas","nos","a","o","as","os"}

def _title_br(s: str) -> str:
    """Title case respeitando artigos/preposições minúsculos."""
    words = str(s).strip().split()
    return " ".join(
        w.capitalize() if (i == 0 or w.lower() not in _MINUSC) else w.lower()
        for i, w in enumerate(words)
    )


# ── Limpeza para import ───────────────────────────────────────────────────────
def _limpar_responsavel(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r'^\d[\d\.\-]{0,13}\s+', '', s)
    return s.strip()

def _parse_turma(t: str):
    t = str(t).strip()
    m = re.search(r'(\d{4})', t)
    ano = int(m.group(1)) if m else None
    nome = re.sub(r'\s*[-–]\s*\d{4}\s*', '', t).strip()
    return re.sub(r'\s+', ' ', nome), ano


# ── Agrupar df por aluno ──────────────────────────────────────────────────────
MAX_RESP = 4  # máximo de colunas de responsável exibidas

def _agrupar(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (turma, nome_aluno). Responsáveis em colunas separadas."""
    if df.empty:
        cols = ["turma", "nome_aluno"] + [f"Responsável {i+1}" for i in range(MAX_RESP)] + ["_ids"]
        return pd.DataFrame(columns=cols)
    grp = (
        df.groupby(["turma", "nome_aluno"], sort=False)
        .apply(lambda g: pd.Series({
            "_resp_list": g["nome_responsavel"].tolist(),
            "_ids": g["id"].tolist(),
        }))
        .reset_index()
    )
    # Expande responsáveis em colunas fixas
    for i in range(MAX_RESP):
        grp[f"Responsável {i+1}"] = grp["_resp_list"].apply(
            lambda lst: lst[i] if i < len(lst) else ""
        )
    grp = grp.drop(columns=["_resp_list"])
    grp = grp.sort_values("turma", key=lambda s: s.map(_sort_turma))
    return grp.reset_index(drop=True)


# ── Página ────────────────────────────────────────────────────────────────────
st.title("👨‍🎓 Alunos e Responsáveis")

# Verifica tabela
try:
    anos_existentes = db.anos_com_alunos()
except Exception as e:
    st.error(
        "**Tabela `alunos` não encontrada no Supabase.**\n\n"
        "Crie a tabela no SQL Editor antes de usar esta página.\n\n"
        f"_(Detalhe: {e})_"
    )
    st.stop()

# Seleção de ano
with st.columns([2, 8])[0]:
    if anos_existentes:
        ano_sel = st.selectbox("Ano letivo", anos_existentes, index=0)
    else:
        ano_sel = st.number_input("Ano letivo", value=2026, step=1, format="%d")

try:
    df_raw = db.carregar_alunos(int(ano_sel))
except Exception as e:
    st.error(f"Erro ao carregar: {e}")
    st.stop()

# Métricas
if not df_raw.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("👦 Alunos", df_raw["nome_aluno"].nunique())
    m2.metric("👪 Responsáveis únicos", df_raw["nome_responsavel"].nunique())
    m3.metric("🏫 Turmas", df_raw["turma"].nunique())
    st.divider()

# ── Abas ──────────────────────────────────────────────────────────────────────
aba_tabela, aba_add, aba_import = st.tabs(
    ["📋 Tabela", "➕ Novo aluno", "📥 Importar Excel"]
)

# ══════════════════════════════════════════════════════════════════════════════
# ABA 1 — Tabela agrupada
# ══════════════════════════════════════════════════════════════════════════════
with aba_tabela:
    if df_raw.empty:
        st.info("Nenhum aluno cadastrado. Use a aba **Importar Excel** para começar.")
    else:
        # ── Container de edição (aparece ACIMA da tabela) ─────────────────────
        edit_container = st.container()

        # ── Filtros ───────────────────────────────────────────────────────────
        fc1, fc2 = st.columns([4, 3])
        busca = fc1.text_input("🔍 Pesquisar", placeholder="aluno, responsável…",
                               key=f"busca_{ano_sel}")
        turmas_disp = sorted(df_raw["turma"].unique(), key=_sort_turma)
        turma_sel = fc2.multiselect("Turma", turmas_disp, key=f"turma_sel_{ano_sel}",
                                    placeholder="Todas as turmas")

        df_filt = df_raw.copy()
        if busca.strip():
            q = busca.strip().lower()
            df_filt = df_filt[
                df_filt["nome_aluno"].str.lower().str.contains(q, na=False) |
                df_filt["nome_responsavel"].str.lower().str.contains(q, na=False)
            ]
        if turma_sel:
            df_filt = df_filt[df_filt["turma"].isin(turma_sel)]

        df_grp = _agrupar(df_filt)
        st.caption(f"{len(df_grp)} aluno(s) · Clique em uma linha para editar ou excluir")

        resp_cols = [f"Responsável {i+1}" for i in range(MAX_RESP)]
        col_config = {
            "turma":      st.column_config.TextColumn("Turma",   width="small"),
            "nome_aluno": st.column_config.TextColumn("Aluno",   width="medium"),
        }
        for c in resp_cols:
            col_config[c] = st.column_config.TextColumn(c, width="medium")

        sel = st.dataframe(
            df_grp[["turma", "nome_aluno"] + resp_cols],
            use_container_width=True,
            hide_index=True,
            height=min(620, 40 + 35 * len(df_grp)),
            selection_mode="single-row",
            on_select="rerun",
            key=f"df_alunos_{ano_sel}",
            column_config=col_config,
        )

        sel_rows = sel.selection.rows if hasattr(sel, "selection") else []

        # ── Preenche o painel de edição (acima da tabela) ─────────────────────
        with edit_container:
            if sel_rows:
                row      = df_grp.iloc[sel_rows[0]]
                ids_aluno = row["_ids"]
                row_key  = "_".join(str(i) for i in sorted(ids_aluno))

                # Inicializa / reseta estado ao trocar de linha
                if st.session_state.get("_edit_row_key") != row_key:
                    st.session_state["_edit_row_key"]   = row_key
                    st.session_state["_edit_resp_list"] = (
                        df_raw[df_raw["id"].isin(ids_aluno)]["nome_responsavel"].tolist()
                    )

                resp_list = st.session_state["_edit_resp_list"]

                # Banner escuro com nome do aluno
                st.markdown(f"""
                <div style="
                    background: #1C2B5F;
                    color: white;
                    padding: 10px 18px;
                    border-radius: 8px 8px 0 0;
                    font-size: 0.82rem;
                    letter-spacing: 0.06em;
                    font-weight: 700;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin-bottom: -2px;
                ">
                    ✏️ &nbsp;EDITANDO
                    <span style="font-weight:400; font-size:0.95rem; letter-spacing:0;">
                        {row['nome_aluno']}
                    </span>
                    <span style="opacity:0.55; font-size:0.78rem; font-weight:400;">
                        · {row['turma']}
                    </span>
                </div>
                """, unsafe_allow_html=True)

                # CSS: borda lateral + fonte menor dentro do container
                st.markdown("""
                <style>
                [data-testid="stVerticalBlockBorderWrapper"] {
                    border-left: 4px solid #1C2B5F !important;
                    border-top: none !important;
                    border-radius: 0 0 8px 8px !important;
                    box-shadow: 0 3px 8px rgba(28,43,95,0.12) !important;
                    filter: brightness(0.91) !important;
                }
                [data-testid="stVerticalBlockBorderWrapper"] label {
                    font-size: 0.82rem !important;
                }
                </style>
                """, unsafe_allow_html=True)

                with st.container(border=True):
                    ec1, ec2 = st.columns(2)
                    turma_e = ec1.selectbox(
                        "Turma", ORDEM_TURMAS,
                        index=_sort_turma(row["turma"]) if row["turma"] in ORDEM_TURMAS else 0,
                        key=f"_edit_turma_{row_key}",
                    )
                    aluno_e = ec2.text_input("Nome do aluno", value=row["nome_aluno"],
                                             key=f"_edit_aluno_{row_key}")

                    # Campos individuais por responsável
                    st.markdown("**Responsáveis**")
                    for i, resp in enumerate(resp_list):
                        r1, r2 = st.columns([12, 1])
                        r1.text_input(
                            f"Responsável {i+1}", value=resp,
                            key=f"_resp_e_{i}_{row_key}",
                            label_visibility="collapsed",
                        )
                        if r2.button("✕", key=f"_del_r_{i}_{row_key}", help="Remover"):
                            cur = [
                                st.session_state.get(f"_resp_e_{j}_{row_key}", resp_list[j])
                                for j in range(len(resp_list))
                            ]
                            cur.pop(i)
                            for j in range(len(resp_list)):
                                st.session_state.pop(f"_resp_e_{j}_{row_key}", None)
                            for j, v in enumerate(cur):
                                st.session_state[f"_resp_e_{j}_{row_key}"] = v
                            st.session_state["_edit_resp_list"] = cur
                            st.rerun()

                    # Botões de ação
                    bc1, bc2, bc3, _ = st.columns([3, 2, 2, 3])
                    if bc1.button("➕ Adicionar responsável", key=f"_btn_add_{row_key}"):
                        cur = [
                            st.session_state.get(f"_resp_e_{j}_{row_key}", resp_list[j])
                            for j in range(len(resp_list))
                        ]
                        cur.append("")
                        for j in range(len(resp_list)):
                            st.session_state.pop(f"_resp_e_{j}_{row_key}", None)
                        for j, v in enumerate(cur):
                            st.session_state[f"_resp_e_{j}_{row_key}"] = v
                        st.session_state["_edit_resp_list"] = cur
                        st.rerun()

                    if bc2.button("💾 Salvar", type="primary", key=f"_btn_save_{row_key}"):
                        novos = [
                            st.session_state.get(f"_resp_e_{j}_{row_key}", resp_list[j]).strip()
                            for j in range(len(resp_list))
                        ]
                        novos = [v for v in novos if v]
                        if not novos:
                            st.error("Informe pelo menos um responsável.")
                        else:
                            for rid in ids_aluno:
                                db.deletar_aluno(int(rid))
                            db.salvar_alunos_lote([
                                {"ano": int(ano_sel),
                                 "turma": st.session_state.get(f"_edit_turma_{row_key}", row["turma"]),
                                 "nome_aluno": st.session_state.get(f"_edit_aluno_{row_key}", row["nome_aluno"]).strip(),
                                 "nome_responsavel": r}
                                for r in novos
                            ])
                            st.session_state.pop("_edit_row_key", None)
                            st.rerun()

                    if bc3.button("🗑️ Excluir aluno", key=f"_btn_del_{row_key}"):
                        for rid in ids_aluno:
                            db.deletar_aluno(int(rid))
                        st.session_state.pop("_edit_row_key", None)
                        st.rerun()

        # Resumo por turma
        st.divider()
        resumo = (
            df_raw.groupby("turma")["nome_aluno"].nunique()
            .reset_index().rename(columns={"nome_aluno": "alunos"})
            .sort_values("turma", key=lambda s: s.map(_sort_turma))
        )
        st.markdown("**📊 Alunos por turma**")
        st.dataframe(resumo, use_container_width=False, hide_index=True,
                     column_config={
                         "turma":  st.column_config.TextColumn("Turma",  width="medium"),
                         "alunos": st.column_config.NumberColumn("Alunos", width="small"),
                     })


# ══════════════════════════════════════════════════════════════════════════════
# ABA 2 — Novo aluno
# ══════════════════════════════════════════════════════════════════════════════
with aba_add:
    st.markdown("Adicione um aluno com um ou mais responsáveis.")
    with st.form("form_novo"):
        c1, c2 = st.columns(2)
        nova_turma = c1.selectbox("Turma", ORDEM_TURMAS)
        novo_aluno = c2.text_input("Nome do aluno")
        st.markdown("**Responsáveis** _(um por linha)_")
        novo_resp_txt = st.text_area("Responsáveis", height=100,
                                     label_visibility="collapsed",
                                     placeholder="Mãe Fulana\nPai Ciclano")
        if st.form_submit_button("➕ Adicionar", type="primary"):
            novos = [r.strip() for r in novo_resp_txt.splitlines() if r.strip()]
            if not novo_aluno.strip() or not novos:
                st.error("Preencha nome do aluno e pelo menos um responsável.")
            else:
                db.salvar_alunos_lote([
                    {"ano": int(ano_sel), "turma": nova_turma,
                     "nome_aluno": novo_aluno.strip(), "nome_responsavel": r}
                    for r in novos
                ])
                st.success(f"✅ {novo_aluno} adicionado com {len(novos)} responsável(eis)!")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ABA 3 — Importar Excel
# ══════════════════════════════════════════════════════════════════════════════
with aba_import:
    st.markdown(
        "Planilha com colunas **Turma**, **Nome da criança** e **Remetente/Destinatario** "
        "(formato exportado do Sponte)."
    )
    SKIP_TURMAS = {"COLÔNIA 2026", "Caiu na conta da Maria CPF"}
    uploaded = st.file_uploader("Selecione o arquivo (.xlsx)", type=["xlsx","xls"],
                                key="upload_alunos")
    if uploaded:
        try:
            df_raw2 = pd.read_excel(uploaded)
            cols_ok = {"Turma","Nome da criança","Remetente/Destinatario"}
            if not cols_ok.issubset(set(df_raw2.columns)):
                st.error(f"Colunas necessárias: {', '.join(cols_ok)}")
            else:
                df_raw2 = df_raw2[~df_raw2["Turma"].isin(SKIP_TURMAS)].dropna(
                    subset=list(cols_ok)).copy()
                df_raw2["nome_responsavel"] = df_raw2["Remetente/Destinatario"].apply(_limpar_responsavel)
                parsed = df_raw2["Turma"].apply(_parse_turma)
                df_raw2["turma"] = [p[0] for p in parsed]
                df_raw2["ano"]   = [p[1] for p in parsed]
                df_raw2["nome_aluno"] = df_raw2["Nome da criança"].str.strip()
                df_proc = df_raw2[["ano","turma","nome_aluno","nome_responsavel"]].drop_duplicates()
                df_proc = df_proc[df_proc["ano"] == int(ano_sel)]

                if df_proc.empty:
                    st.warning(f"Nenhum registro para {ano_sel} no arquivo.")
                else:
                    st.success(f"**{df_proc['nome_aluno'].nunique()} alunos** encontrados.")
                    grp_prev = _agrupar(df_proc.assign(id=range(len(df_proc))))
                    prev_cols = ["turma","nome_aluno"] + [f"Responsável {i+1}" for i in range(MAX_RESP)]
                    st.dataframe(grp_prev[prev_cols], use_container_width=True, hide_index=True)

                    modo = st.radio("Como importar?",
                                    ["Adicionar aos existentes",
                                     "Substituir todos os registros do ano"])
                    if st.button("📥 Confirmar importação", type="primary"):
                        if modo == "Substituir todos os registros do ano":
                            db.limpar_alunos_ano(int(ano_sel))
                        db.salvar_alunos_lote(df_proc.to_dict("records"))
                        st.success(f"✅ {len(df_proc)} registros importados!")
                        st.rerun()
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")


