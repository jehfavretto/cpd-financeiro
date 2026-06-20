"""
Cliente Supabase — todas as operações de leitura e escrita no banco de dados.
"""
from __future__ import annotations
import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date
from core.parser import _normalizar_data_banco


# ── Conexão ──────────────────────────────────────────────────────────────────

@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


# ── PlanoDeContas ─────────────────────────────────────────────────────────────

def salvar_plano_contas(mes: int, ano: int, plano_df: pd.DataFrame):
    """Upsert dos valores do PlanoDeContas para o mês."""
    client = get_client()
    rows = [
        {
            "mes": mes,
            "ano": ano,
            "codigo": str(r["codigo"]).strip(),
            "descricao": str(r["descricao"]).strip(),
            "valor": float(r["valor"]),
        }
        for _, r in plano_df.iterrows()
    ]
    if rows:
        client.table("plano_contas").upsert(rows, on_conflict="mes,ano,codigo").execute()
    carregar_plano_contas.clear()
    carregar_plano_contas_multiplos.clear()
    meses_com_dados.clear()


@st.cache_data(ttl=300)
def carregar_plano_contas(mes: int, ano: int) -> pd.DataFrame:
    client = get_client()
    res = (
        client.table("plano_contas")
        .select("codigo, descricao, valor")
        .eq("mes", mes)
        .eq("ano", ano)
        .execute()
    )
    if not res.data:
        return pd.DataFrame(columns=["codigo", "descricao", "valor"])
    return pd.DataFrame(res.data)


@st.cache_data(ttl=300)
def carregar_plano_contas_multiplos(meses: list[tuple[int, int]]) -> pd.DataFrame:
    """Retorna PlanoDeContas para vários (mes, ano), com colunas mes e ano."""
    client = get_client()
    dfs = []
    for mes, ano in meses:
        res = (
            client.table("plano_contas")
            .select("mes, ano, codigo, descricao, valor")
            .eq("mes", mes)
            .eq("ano", ano)
            .execute()
        )
        if res.data:
            dfs.append(pd.DataFrame(res.data))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


@st.cache_data(ttl=300)
def meses_com_dados(ano: int) -> list[int]:
    """Retorna lista de meses com PlanoDeContas preenchido para o ano."""
    client = get_client()
    res = (
        client.table("plano_contas")
        .select("mes")
        .eq("ano", ano)
        .execute()
    )
    if not res.data:
        return []
    return sorted(set(r["mes"] for r in res.data))


# ── Lançamentos Sponte ────────────────────────────────────────────────────────

def salvar_lancamentos_sponte(mes: int, ano: int, df: pd.DataFrame):
    client = get_client()
    client.table("lancamentos_sponte").delete().eq("mes", mes).eq("ano", ano).execute()
    rows = [
        {
            "mes": mes,
            "ano": ano,
            "data": str(r["data"]),
            "data_rep": str(r["data_rep"]),
            "categoria": str(r["categoria"]),
            "es": str(r["es"]),
            "origem_destino": str(r["origem_destino"]),
            "valor": float(r["valor"]),
        }
        for _, r in df.iterrows()
    ]
    if rows:
        client.table("lancamentos_sponte").insert(rows).execute()
    carregar_lancamentos_sponte.clear()


@st.cache_data(ttl=60)
def carregar_lancamentos_sponte(mes: int, ano: int) -> pd.DataFrame:
    client = get_client()
    res = (
        client.table("lancamentos_sponte")
        .select("*")
        .eq("mes", mes)
        .eq("ano", ano)
        .order("data")
        .execute()
    )
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["valor"] = df["valor"].abs()
    df["es"] = df["es"].str.strip()
    return df


# ── Transações Banco ─────────────────────────────────────────────────────────

def salvar_transacoes_banco(mes: int, ano: int, df: pd.DataFrame):
    client = get_client()
    client.table("transacoes_banco").delete().eq("mes", mes).eq("ano", ano).execute()
    rows = [
        {
            "mes": mes,
            "ano": ano,
            "data_mov": str(r["data_mov"]),
            "nr_doc": str(r.get("nr_doc", "")),
            "historico": str(r["historico"]),
            "valor": float(r["valor_num"]),
            "deb_cred": str(r["deb_cred"]),
            "origem_destino": str(r.get("origem_destino", "") or ""),
        }
        for _, r in df.iterrows()
    ]
    if rows:
        client.table("transacoes_banco").insert(rows).execute()
    carregar_transacoes_banco.clear()


@st.cache_data(ttl=60)
def carregar_transacoes_banco(mes: int, ano: int) -> pd.DataFrame:
    client = get_client()
    res = (
        client.table("transacoes_banco")
        .select("*")
        .eq("mes", mes)
        .eq("ano", ano)
        .execute()
    )
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    df["data_mov"] = df["data_mov"].apply(_normalizar_data_banco)
    df["deb_cred"] = df["deb_cred"].str.strip().replace({"C": "E", "D": "S"})
    df["valor"] = df["valor"].abs()
    if "origem_destino" not in df.columns:
        df["origem_destino"] = ""
    else:
        df["origem_destino"] = df["origem_destino"].fillna("")
    return df


# ── Saldos ────────────────────────────────────────────────────────────────────

def salvar_saldos(
    mes: int, ano: int,
    banco: float, aplicacao: float, caixa: float,
    rendimento_aplicacao: float = 0.0,
    resgate_aplicacao: float = 0.0,
    diferenca_caixa: float = 0.0,
):
    client = get_client()
    client.table("saldos").upsert(
        {
            "mes": mes, "ano": ano,
            "saldo_banco": banco,
            "saldo_aplicacao": aplicacao,
            "saldo_caixa": caixa,
            "rendimento_aplicacao": rendimento_aplicacao,
            "resgate_aplicacao": resgate_aplicacao,
            "diferenca_caixa": diferenca_caixa,
        },
        on_conflict="mes,ano",
    ).execute()
    carregar_saldos.clear()
    carregar_saldos_ano.clear()


@st.cache_data(ttl=60)
def carregar_saldos(mes: int, ano: int) -> dict:
    client = get_client()
    res = (
        client.table("saldos")
        .select("*")
        .eq("mes", mes)
        .eq("ano", ano)
        .execute()
    )
    if res.data:
        return res.data[0]
    return {
        "saldo_banco": 0.0, "saldo_aplicacao": 0.0, "saldo_caixa": 0.0,
        "rendimento_aplicacao": 0.0, "resgate_aplicacao": 0.0, "diferenca_caixa": 0.0,
    }



@st.cache_data(ttl=300)
def carregar_saldos_ano(ano: int) -> pd.DataFrame:
    client = get_client()
    res = (
        client.table("saldos")
        .select("*")
        .eq("ano", ano)
        .order("mes")
        .execute()
    )
    if not res.data:
        return pd.DataFrame()
    return pd.DataFrame(res.data)


# ── Ajustes Manuais (AR / AD) ────────────────────────────────────────────────

def salvar_ajuste(mes: int, ano: int, tipo: str, valor: float):
    """tipo = 'AR' ou 'AD'"""
    client = get_client()
    client.table("ajustes").upsert(
        {"mes": mes, "ano": ano, "tipo": tipo, "valor": valor},
        on_conflict="mes,ano,tipo",
    ).execute()
    carregar_ajustes.clear()


@st.cache_data(ttl=300)
def carregar_ajustes(mes: int, ano: int) -> dict:
    client = get_client()
    res = (
        client.table("ajustes")
        .select("tipo, valor")
        .eq("mes", mes)
        .eq("ano", ano)
        .execute()
    )
    result = {"AR": 0.0, "AD": 0.0}
    for row in (res.data or []):
        result[row["tipo"]] = float(row["valor"])
    return result


# ── Conciliacoes ─────────────────────────────────────────────────────────────

def salvar_conciliacao(
    mes: int,
    ano: int,
    tipo: str,
    sponte_chave: str | None = None,
    banco_chave: str | None = None,
    justificativa: str | None = None,
):
    """Salva um vínculo manual ou registro de ignorado."""
    client = get_client()
    client.table("conciliacoes").insert({
        "mes": mes,
        "ano": ano,
        "tipo": tipo,
        "sponte_chave": sponte_chave,
        "banco_chave": banco_chave,
        "justificativa": justificativa,
    }).execute()


def carregar_conciliacoes(mes: int, ano: int) -> list[dict]:
    client = get_client()
    res = (
        client.table("conciliacoes")
        .select("*")
        .eq("mes", mes)
        .eq("ano", ano)
        .execute()
    )
    return res.data or []


def deletar_conciliacao(id_conc: int):
    client = get_client()
    client.table("conciliacoes").delete().eq("id", id_conc).execute()


def limpar_conciliacoes_mes(mes: int, ano: int):
    """Remove todas as conciliações de um mês (ao re-importar os dados)."""
    client = get_client()
    client.table("conciliacoes").delete().eq("mes", mes).eq("ano", ano).execute()


# ── Alunos ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def carregar_alunos(ano: int) -> pd.DataFrame:
    client = get_client()
    res = (
        client.table("alunos")
        .select("id, ano, turma, nome_aluno, nome_responsavel")
        .eq("ano", ano)
        .order("turma")
        .order("nome_aluno")
        .order("id")          # mantém ordem de inserção dos responsáveis
        .execute()
    )
    if not res.data:
        return pd.DataFrame(columns=["id", "ano", "turma", "nome_aluno", "nome_responsavel"])
    return pd.DataFrame(res.data)


@st.cache_data(ttl=300)
def anos_com_alunos() -> list[int]:
    client = get_client()
    res = client.table("alunos").select("ano").execute()
    if not res.data:
        return []
    return sorted(set(r["ano"] for r in res.data), reverse=True)


def salvar_alunos_lote(rows: list[dict]):
    """Insere uma lista de alunos de uma vez (sem deduplicar — use limpar_alunos_ano antes)."""
    client = get_client()
    if rows:
        client.table("alunos").insert(rows).execute()
    carregar_alunos.clear()


def upsert_aluno(ano: int, turma: str, nome_aluno: str, nome_responsavel: str, id: int | None = None):
    """Cria ou atualiza um aluno. Se id informado, faz update; senão insert."""
    client = get_client()
    payload = {
        "ano": ano,
        "turma": turma.strip(),
        "nome_aluno": nome_aluno.strip(),
        "nome_responsavel": nome_responsavel.strip(),
    }
    if id:
        client.table("alunos").update(payload).eq("id", id).execute()
    else:
        client.table("alunos").insert(payload).execute()


def deletar_aluno(id: int):
    client = get_client()
    client.table("alunos").delete().eq("id", id).execute()
    carregar_alunos.clear()


def limpar_alunos_ano(ano: int):
    """Remove todos os alunos de um ano (antes de re-importar)."""
    client = get_client()
    client.table("alunos").delete().eq("ano", ano).execute()
    carregar_alunos.clear()


# ── Lançamentos Caixa ────────────────────────────────────────────────────────

def salvar_lancamentos_caixa(mes: int, ano: int, df: pd.DataFrame):
    client = get_client()
    client.table("lancamentos_caixa").delete().eq("mes", mes).eq("ano", ano).execute()
    rows = [
        {
            "mes": mes, "ano": ano,
            "data_mov":  str(r["data_mov"]),
            "descricao": str(r.get("descricao", "") or ""),
            "categoria": str(r.get("categoria", "") or ""),
            "valor":     float(r["valor"]),
            "deb_cred":  str(r["deb_cred"]),
        }
        for _, r in df.iterrows()
    ]
    if rows:
        client.table("lancamentos_caixa").insert(rows).execute()
    carregar_lancamentos_caixa.clear()


@st.cache_data(ttl=300)
def carregar_lancamentos_caixa(mes: int, ano: int) -> pd.DataFrame:
    client = get_client()
    res = (
        client.table("lancamentos_caixa")
        .select("*")
        .eq("mes", mes)
        .eq("ano", ano)
        .order("data_mov")
        .execute()
    )
    if not res.data:
        return pd.DataFrame(columns=["id", "mes", "ano", "data_mov", "descricao", "valor", "deb_cred"])
    df = pd.DataFrame(res.data)
    df["valor"] = df["valor"].abs()
    return df


def buscar_aluno_por_responsavel(nome_responsavel: str, ano: int) -> list[dict]:
    """Retorna alunos cujo nome_responsavel contém a substring (case-insensitive)."""
    client = get_client()
    res = (
        client.table("alunos")
        .select("id, turma, nome_aluno, nome_responsavel")
        .eq("ano", ano)
        .ilike("nome_responsavel", f"%{nome_responsavel}%")
        .execute()
    )
    return res.data or []
