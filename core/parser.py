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


_MINUSC = {"de","da","do","dos","das","e","em","na","no","nas","nos","a","o","as","os"}

def _title_br(s: str) -> str:
    words = str(s).strip().split()
    return " ".join(
        w.capitalize() if (i == 0 or w.lower() not in _MINUSC) else w.lower()
        for i, w in enumerate(words)
    )

def _limpar_nome_banco(nome: str) -> str:
    """Remove prefixo numérico de CNPJ ('52 053 009 NOME...') e aplica Title Case."""
    nome = str(nome).strip()
    if not nome or nome.lower() == "nan":
        return ""
    # Remove dígitos/espaços do início antes do primeiro caractere alfabético
    nome = re.sub(r'^[\d\s]+(?=[A-Za-z])', '', nome).strip()
    return _title_br(nome) if nome.isupper() else nome

_DE_PARA_HISTORICO = {
    "APLICACAO FDO - CLIENTE":  "Aplicação Financeira",
    "MENSALIDADE CESTA SERVICO": "Tarifa Bancária",
    "DEPOSITO DINH LOTERICO":   "Depósito Lotérico",
    "COMPRA CARTAO DEBITO":     "Cartão de Débito",
    "PAG BOLETO IBC":           "Pagamento Boleto",
    "PAGAMENTO TELEFONE IBC":   "Telefone",
}

def parse_banco_xlsx(file_bytes_or_path) -> pd.DataFrame:
    """
    Lê o extrato CEF no novo formato XLSX.
    Retorna DataFrame normalizado igual ao parse_banco_txt:
    data_mov (DD/MM/YYYY), nr_doc, historico, valor_num, deb_cred, origem_destino.
    """
    # Copia para BytesIO fresco — evita problema de posição de stream com UploadedFile
    import io as _io
    if hasattr(file_bytes_or_path, "read"):
        file_bytes_or_path.seek(0)
        _content = file_bytes_or_path.read()
        _file = _io.BytesIO(_content)
    else:
        _file = file_bytes_or_path
    raw = pd.read_excel(_file, dtype=str)
    # Linha 0 é o cabeçalho real
    raw.columns = raw.iloc[0]
    raw = raw.iloc[1:].reset_index(drop=True)
    # Remove linhas de SALDO DIA (não são transações)
    raw = raw[raw["Histórico"] != "SALDO DIA"].copy()

    # Data de movimento
    raw["data_mov"] = pd.to_datetime(
        raw["Data Movimento"], format="%d/%m/%Y", errors="coerce"
    ).dt.strftime("%d/%m/%Y").fillna(raw["Data Movimento"])

    # Documento
    raw["nr_doc"] = raw["Documento"].fillna("").str.strip()

    # Histórico
    raw["historico"] = raw["Histórico"].str.strip()

    # Valor: suporta formato BR ("- 1.850,00") e numérico padrão ("-1850.0")
    def _parse_val_xlsx(v):
        # Se pandas já leu como número, usa direto
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s or s.lower() == "nan":
            return 0.0
        # Detecta sinal negativo ANTES de limpar (o Excel usa '-', '−' ou '\xa0' após o '-')
        negative = "-" in s or "−" in s
        # Extrai apenas dígitos, ponto e vírgula — remove tudo mais (espaço, \xa0, etc.)
        digits = re.sub(r"[^\d,.]", "", s)
        if not digits:
            return 0.0
        # Formato BR: vírgula como separador decimal ("1.850,00" → "1850.00")
        if "," in digits:
            digits = digits.replace(".", "").replace(",", ".")
        try:
            val = float(digits)
            return -val if negative else val
        except ValueError:
            return 0.0

    raw["_val_signed"] = raw["Valor Lançamento"].apply(_parse_val_xlsx)
    raw["valor_num"]   = raw["_val_signed"].abs()
    raw["deb_cred"]    = raw["_val_signed"].apply(lambda v: "S" if v < 0 else "E")

    # Origem/destino: Nome/Razão Social > de:para do histórico
    def _origem(row):
        nome = str(row.get("Nome/Razão Social", "")).strip()
        hist = str(row.get("historico", "")).strip()
        if nome and nome.lower() not in ("nan", ""):
            return _limpar_nome_banco(nome)
        return _DE_PARA_HISTORICO.get(hist, hist)

    raw["origem_destino"] = raw.apply(_origem, axis=1)

    return raw[["data_mov", "nr_doc", "historico", "valor_num", "deb_cred", "origem_destino"]].reset_index(drop=True)


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

    # Formato antigo não tem origem_destino
    df["origem_destino"] = ""

    return df


def parse_caixa_xlsx(file_bytes_or_path) -> pd.DataFrame:
    """
    Lê planilha de caixa físico.
    Colunas esperadas: Data | Descrição | Valor | E/S
    Retorna: data_mov, descricao, valor (abs), deb_cred (E/S)
    """
    import io as _io, unicodedata as _ud
    if hasattr(file_bytes_or_path, "read"):
        file_bytes_or_path.seek(0)
        _file = _io.BytesIO(file_bytes_or_path.read())
    else:
        _file = file_bytes_or_path

    df = pd.read_excel(_file, dtype=str)

    def _nc(c):
        c = _ud.normalize("NFD", str(c).strip().lower())
        return "".join(ch for ch in c if _ud.category(ch) != "Mn")

    df.columns = [_nc(c) for c in df.columns]

    col_map = {}
    for c in df.columns:
        if c in ("data", "dt", "data_mov", "data mov"):          col_map.setdefault("data_mov", c)
        elif c in ("descricao", "descricacao", "historico",
                   "descr", "desc", "descricao", "descricao"):   col_map.setdefault("descricao", c)
        elif c in ("valor", "value", "vlr", "vl"):               col_map.setdefault("valor", c)
        elif c in ("e/s", "es", "tipo", "entrada/saida",
                   "entrada_saida", "deb_cred"):                  col_map.setdefault("deb_cred", c)

    missing = [k for k in ("data_mov", "descricao", "valor", "deb_cred") if k not in col_map]
    if missing:
        raise ValueError(
            f"Colunas não encontradas: {missing}. "
            "A planilha precisa ter: Data, Descrição, Valor, E/S"
        )

    df = df.rename(columns={v: k for k, v in col_map.items()})
    df = df.dropna(subset=["data_mov", "valor"]).copy()

    df["data_mov"] = pd.to_datetime(
        df["data_mov"], format="%d/%m/%Y", errors="coerce"
    ).dt.strftime("%d/%m/%Y").fillna(df["data_mov"])

    def _pv(v):
        if isinstance(v, (int, float)):
            return abs(float(v))
        s = str(v).strip().replace("\xa0", "").replace(" ", "")
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        try:
            return abs(float(s))
        except ValueError:
            return 0.0

    df["valor"] = df["valor"].apply(_pv)

    _es_map = {
        "e": "E", "entrada": "E", "entradas": "E", "c": "E", "credito": "E", "1": "E",
        "s": "S", "saida": "S", "saída": "S", "saidas": "S", "d": "S", "debito": "S", "0": "S",
    }
    df["deb_cred"] = df["deb_cred"].fillna("E").apply(
        lambda v: _es_map.get(str(v).strip().lower(), "E")
    )
    df["descricao"] = df["descricao"].fillna("").str.strip()

    return df[["data_mov", "descricao", "valor", "deb_cred"]].reset_index(drop=True)


# De:para para históricos sem nome associado (XLSX novo formato)
_DEPARA_HISTORICO_BANCO: dict[str, str] = {
    "APLICACAO FDO - CLIENTE":  "Aplicação Financeira",
    "MENSALIDADE CESTA SERVICO": "Tarifa Bancária",
    "DEPOSITO DINH LOTERICO":   "Depósito Lotérico",
    "COMPRA CARTAO DEBITO":     "Cartão de Débito",
    "PAG BOLETO IBC":           "Pagamento Boleto",
    "PAGAMENTO TELEFONE IBC":   "Pagamento Telefone",
    "PIX ENVIADO":              "PIX Enviado",
    "PIX RECEBIDO":             "PIX Recebido",
}

_MINUSC_BR = {"de","da","do","dos","das","e","em","na","no","nas","nos","a","o","as","os"}

def _title_br_nome(s: str) -> str:
    """Title case respeitando artigos/preposições minúsculos do português."""
    words = str(s).strip().split()
    return " ".join(
        w.capitalize() if (i == 0 or w.lower() not in _MINUSC_BR) else w.lower()
        for i, w in enumerate(words)
    )

def _limpar_nome_banco(nome: str) -> str:
    """
    Limpa o Nome/Razão Social do extrato CEF.
    Remove prefixo numérico (ex: '52 053 009 MONICA...' → 'Monica...').
    Converte CAIXA ALTA para Title Case BR.
    """
    nome = str(nome).strip()
    if not nome or nome.lower() in ("nan", "none", ""):
        return ""
    # Remove prefixo de dígitos e espaços antes do primeiro caractere letra
    # Ex: "52 053 009 MONICA ERTHAL" → "MONICA ERTHAL"
    nome = re.sub(r'^[\d\s]+(?=[A-Za-zÀ-ÿ])', '', nome).strip()
    # Title case se estiver em caixa alta
    if nome.upper() == nome:
        nome = _title_br_nome(nome)
    return nome


def parse_banco_xlsx(file_bytes_or_path) -> pd.DataFrame:
    """
    Lê o extrato da CEF no novo formato XLSX.
    Colunas: Data Lancamento | Data Movimento | Histórico | Documento |
             Valor Lançamento | Saldo | CPF/CNPJ | Nome/Razão Social
    Retorna DataFrame compatível com parse_banco_txt + coluna origem_destino.
    """
    raw = pd.read_excel(file_bytes_or_path, dtype=str)
    # Primeira linha é o cabeçalho real (linha 0 do excel é "Extrato de ...")
    raw.columns = raw.iloc[0]
    raw = raw.iloc[1:].reset_index(drop=True)

    # Remove linhas de saldo do dia (não são transações)
    raw = raw[raw["Histórico"].fillna("") != "SALDO DIA"].copy()
    raw = raw.dropna(subset=["Data Movimento"]).reset_index(drop=True)

    # Data
    raw["data_mov"] = raw["Data Movimento"].apply(_normalizar_data_banco)

    # Documento
    raw["nr_doc"] = raw["Documento"].fillna("").str.strip()

    # Histórico
    raw["historico"] = raw["Histórico"].str.strip()

    # Valor: "2.513,00" → 2513.0 | "- 1.850,00" → 1850.0
    val_str = (
        raw["Valor Lançamento"]
        .str.replace(r"\s", "", regex=True)   # remove espaços
        .str.replace(".", "", regex=False)     # remove separador de milhar
        .str.replace(",", ".", regex=False)    # vírgula → ponto decimal
    )
    val_signed = pd.to_numeric(val_str, errors="coerce").fillna(0)
    raw["valor_num"] = val_signed.abs()

    # deb_cred: negativo = S (saída), positivo = E (entrada)
    raw["deb_cred"] = val_signed.apply(lambda v: "S" if v < 0 else "E")

    # Origem/destino: usa Nome/Razão Social ou de:para do histórico
    def _get_origem(row):
        nome = str(row.get("Nome/Razão Social", "")).strip()
        hist = str(row.get("historico", "")).strip()
        if nome and nome.lower() not in ("nan", "none", ""):
            return _limpar_nome_banco(nome)
        return _DEPARA_HISTORICO_BANCO.get(hist, hist)

    raw["origem_destino"] = raw.apply(_get_origem, axis=1)

    return raw[["data_mov", "nr_doc", "historico", "valor_num", "deb_cred", "origem_destino"]].reset_index(drop=True)


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
