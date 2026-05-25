"""
Cliente Supabase — todas as operações de leitura e escrita no banco de dados.
"""
from __future__ import annotations
import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date


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
    # Upsert com conflict em (mes, ano, codigo)
    client.table("plano_contas").upsert(rows, on_conflict="mes,ano,codigo").execute()


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
    # Apaga os anteriores do mesmo mês
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
    client.table("lancamentos_sponte").insert(rows).execute()


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
        }
        for _, r in df.iterrows()
    ]
    client.table("transacoes_banco").insert(rows).execute()


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
    return pd.DataFrame(res.data)


# ── Saldos ────────────────────────────────────────────────────────────────────

def salvar_saldos(mes: int, ano: int, banco: float, aplicacao: float, caixa: float):
    client = get_client()
    client.table("saldos").upsert(
        {"mes": mes, "ano": ano,
         "saldo_banco": banco, "saldo_aplicacao": aplicacao, "saldo_caixa": caixa},
        on_conflict="mes,ano",
    ).execute()


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
    return {"saldo_banco": 0.0, "saldo_aplicacao": 0.0, "saldo_caixa": 0.0}


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
    try:
        res = (
            client.table("conciliacoes")
            .select("*")
            .eq("mes", mes)
            .eq("ano", ano)
            .execute()
        )
        return res.data or []
    except Exception as e:
        # Expõe o erro real para diagnóstico
        raise RuntimeError(f"Erro ao carregar conciliações: {type(e).__name__}: {e}") from e


def deletar_conciliacao(id_conc: int):
    client = get_client()
    client.table("conciliacoes").delete().eq("id", id_conc).execute()


def limpar_conciliacoes_mes(mes: int, ano: int):
    """Remove todas as conciliações de um mês (ao re-importar os dados)."""
    client = get_client()
    client.table("conciliacoes").delete().eq("mes", mes).eq("ano", ano).execute()
