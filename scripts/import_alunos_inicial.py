"""
Script de uso único: importa alunos de Pasta.alunos.xlsx para o Supabase.
Execute uma vez após criar a tabela alunos.

Uso:
    cd "/Users/jessica/Applications/CPD - App"
    python scripts/import_alunos_inicial.py
"""
import sys
import re
from pathlib import Path

# Garante que o root do projeto está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

# Carrega secrets do Streamlit para pegar credenciais do Supabase
from supabase import create_client

EXCEL = Path.home() / "Downloads" / "Pasta.alunos.xlsx"
SKIP_TURMAS = {"COLÔNIA 2026", "Caiu na conta da Maria CPF"}
ANO = 2026


def limpar_responsavel(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r'^\d[\d\.\-]{0,13}\s+', '', s)
    return s.strip()


def parse_turma(t: str):
    t = str(t).strip()
    m = re.search(r'(\d{4})', t)
    ano = int(m.group(1)) if m else ANO
    nome = re.sub(r'\s*[-–]\s*\d{4}\s*', '', t).strip()
    nome = re.sub(r'\s+', ' ', nome)
    return nome, ano


def main():
    # Ler credenciais do secrets.toml
    secrets_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        print("ERRO: .streamlit/secrets.toml não encontrado")
        sys.exit(1)

    # Lê url e key direto do arquivo (compatível com Python 3.9+)
    url, key = None, None
    with open(secrets_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("url"):
                url = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("key"):
                key = line.split("=", 1)[1].strip().strip('"')
    if not url or not key:
        print("ERRO: não foi possível ler url/key do secrets.toml")
        sys.exit(1)
    client = create_client(url, key)

    # Ler Excel
    print(f"Lendo {EXCEL}...")
    df = pd.read_excel(EXCEL)
    df = df[~df["Turma"].isin(SKIP_TURMAS)].dropna(
        subset=["Turma", "Nome da criança", "Remetente/Destinatario"]
    ).copy()

    df["nome_responsavel"] = df["Remetente/Destinatario"].apply(limpar_responsavel)
    parsed = df["Turma"].apply(parse_turma)
    df["turma"] = [p[0] for p in parsed]
    df["ano"]   = [p[1] for p in parsed]
    df["nome_aluno"] = df["Nome da criança"].str.strip()

    # Deduplica
    df = df[["ano", "turma", "nome_aluno", "nome_responsavel"]].drop_duplicates()
    df = df[df["ano"] == ANO]

    print(f"Registros a inserir: {len(df)}")

    # Limpa ano antes de inserir (idempotente)
    print("Limpando registros existentes de 2026...")
    client.table("alunos").delete().eq("ano", ANO).execute()

    # Insere em lotes de 50
    rows = df.to_dict("records")
    BATCH = 50
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i+BATCH]
        client.table("alunos").insert(batch).execute()
        print(f"  Inseridos {min(i+BATCH, len(rows))}/{len(rows)}")

    print("✅ Importação concluída!")


if __name__ == "__main__":
    main()
