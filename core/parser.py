"""
Parsers para os arquivos exportados do Sponte e da CEF.
Lógica extraída do processar_mes.py existente.
"""
import re
import unicodedata
import pandas as pd
from datetime import datetime


MESES_ABREV = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
    5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


def _parse_valor_br(v):
    """Converte '1.800,00' → 1800.0"""
    if pd.isna(v) or str(v).strip() == "":
        return 0.0
    s = str(v).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _normalizar_data_banco(s: str) -> str:
    """Normaliza data do banco para DD/MM/YYYY, tentando vários formatos."""
    s = str(s).strip()
    for fmt in ("%Y%m%d", "%d%m%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.strptime(s, fmt)
            return f"{d.day:02d}/{d.month:02d}/{d.year}"
        except ValueError:
            continue
    return s  # fallback


def parse_sponte_fluxo(file_bytes_or_path) -> pd.DataFrame:
    """
    Lê o FluxoCaixa exportado do Sponte (.xls).
    Retorna DataFrame: data, data_rep, categoria, es, origem_destino, valor.
    Valor sempre positivo (o campo es indica a direção).
    """
    raw = pd.read_excel(file_bytes_or_path, header=None, skiprows=8, dtype=str)
    mask = raw[0].apply(
        lambda x: isinstance(x, str) and len(x) == 10 and x[2] == "/" and x[5] == "/"
    )
    data = raw[mask].reset_index(drop=True)

    df = pd.DataFrame({
        "data":           data[0],
        "data_rep":       data[4],
        "categoria":      data[6].fillna(""),
        "es":             data[7].str.strip(),
        "origem_destino": data[8].fillna(""),
        "valor":          data[11].apply(_parse_valor_br).abs(),  # sempre positivo
    })

    # Converte datas string → date
    df["data"]     = pd.to_datetime(df["data"],     format="%d/%m/%Y").dt.date
    df["data_rep"] = pd.to_datetime(df["data_rep"], format="%d/%m/%Y").dt.date

    return df


def parse_banco_txt(file_bytes_or_path) -> pd.DataFrame:
    """
    Lê o extrato da CEF (.txt, separador ';').
    Retorna DataFrame normalizado: data_mov em DD/MM/YYYY, es em E/S, valor positivo.
    """
    df = pd.read_csv(
        file_bytes_or_path, sep=";", encoding="latin-1",
        dtype=str, quotechar='"',
    )
    df.columns = ["conta", "data_mov", "nr_doc", "historico", "valor", "deb_cred"]
    df = df.dropna(subset=["data_mov"]).reset_index(drop=True)

    # Normaliza valor: sempre positivo
    df["valor_num"] = df["valor"].str.replace(",", ".").astype(float).abs()

    # Normaliza data para DD/MM/YYYY
    df["data_mov"] = df["data_mov"].apply(_normalizar_data_banco)

    # Normaliza C/D → E/S
    df["deb_cred"] = df["deb_cred"].str.strip().map({"C": "E", "D": "S"}).fillna("S")

    return df


def _normalizar(s: str) -> str:
    """Normaliza string para matching: minúsculas, sem acento, só alfanumérico."""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_sponte_plano(file_bytes_or_path) -> pd.DataFrame:
    """
    Lê o PlanoDeContas exportado do Sponte (.xls).
    Retorna DataFrame: codigo, descricao, valor.
    Apenas linhas estruturadas (prefixo ¯).
    """
    raw = pd.read_excel(file_bytes_or_path, header=None, dtype=str)
    records = []

    for _, row in raw.iterrows():
        col0 = str(row[0]).strip() if pd.notna(row[0]) else ""
        col6 = str(row[6]).strip() if (len(row) > 6 and pd.notna(row[6])) else ""

        if "¯" not in col0:
            continue
        if not col6 or col6 in ("nan", "None", ""):
            continue

        m = re.search(r"(\d+(?:\.\d+)*)-(.+)", col0)
        if not m:
            continue

        codigo    = m.group(1).strip()
        descricao = re.sub(r"\.{2,}\s*$", "", m.group(2)).strip()

        val_str = col6.replace("R$", "").strip().replace(".", "").replace(",", ".")
        try:
            valor = float(val_str)
        except ValueError:
            continue

        records.append({"codigo": codigo, "descricao": descricao, "valor": valor})

    if not records:
        return pd.DataFrame(columns=["codigo", "descricao", "valor"])
    return pd.DataFrame(records)


def detectar_mes_ano(sponte_df: pd.DataFrame) -> tuple[int, int]:
    """Retorna (mes, ano) a partir da primeira linha do FluxoCaixa."""
    d = sponte_df["data"].iloc[0]
    return d.month, d.year


def match_plano_contas(plano_sponte: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe o DataFrame do Sponte PlanoDeContas e retorna o mesmo com
    matching validado (código + descrição). Usado para insert no DB.
    Não precisa do Book aqui — guardamos os dados do Sponte diretamente.
    """
    return plano_sponte.copy()
