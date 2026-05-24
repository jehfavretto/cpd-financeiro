"""
Lógica da Demonstração de Fluxo de Caixa (DFC).
Replica a estrutura da aba Resumo do Book Excel.

Regra de sinal:
  - 1.xx RECEITAS        → positivo  (valor arrecadado entra)
  - 2.xx CUSTOS          → negativo  (PlanoDeContas guarda positivo, aqui invertemos)
  - 3.xx DESPESAS        → negativo
  - 4.xx IMPOSTOS        → negativo
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


# ── Hierarquia da DFC ─────────────────────────────────────────────────────────

GRUPOS = {
    "1.01": "RECEITA EDUCACIONAL PRINCIPAL",
    "1.02": "RECEITA COMPLEMENTAR EDUCACIONAL",
    "1.03": "RECEITA COM ALIMENTAÇÃO",
    "1.04": "RECEITA COM EVENTOS",
    "1.05": "OUTRAS RECEITAS",
    "2.01": "CUSTOS COM PROFESSORES",
    "2.02": "CUSTOS COM ALIMENTAÇÕES",
    "2.03": "CUSTOS COM MATERIAIS PEDAGÓGICOS",
    "2.04": "CUSTOS COM EVENTOS PEDAGÓGICOS",
    "3.01": "DESPESAS ADMINISTRATIVAS",
    "3.02": "DESPESAS COM PESSOAL",
    "3.03": "DESPESAS COM DIRETORIA",
    "3.04": "DESPESAS COM IMÓVEL",
    "3.05": "DESPESAS COMERCIAL",
    "3.06": "DESPESAS FINANCEIRAS",
    "4.01": "Impostos sobre Vendas e sobre Serviços",
}

SECOES = {
    "1.": {"label": "RECEITAS",             "sinal":  1},
    "2.": {"label": "CUSTOS DIRETOS",       "sinal": -1},
    "3.": {"label": "DESPESAS OPERACIONAIS","sinal": -1},
    "4.": {"label": "IMPOSTOS",             "sinal": -1},
}


def _secao(codigo: str) -> Optional[str]:
    """Retorna o prefixo de seção ('1.', '2.', etc.) para um código."""
    if codigo and codigo[0].isdigit():
        return codigo[0] + "."
    return None


def _grupo(codigo: str) -> Optional[str]:
    """Retorna o prefixo de grupo ('1.01', '2.03', etc.)."""
    parts = codigo.split(".")
    if len(parts) >= 2:
        return parts[0] + "." + parts[1]
    return None


@dataclass
class LinhasDFC:
    """Resultado pré-calculado da DFC para um ou mais meses."""
    # { secao_prefix: { grupo_prefix: { codigo: valor_signed } } }
    dados: dict = field(default_factory=dict)
    ar: float = 0.0   # Ajuste Receita (manual)
    ad: float = 0.0   # Ajuste Despesa (manual)

    # Saldos
    saldo_anterior: float = 0.0
    saldo_banco: float = 0.0
    saldo_aplicacao: float = 0.0
    saldo_caixa: float = 0.0

    def total_secao(self, secao: str) -> float:
        grupos = self.dados.get(secao, {})
        return sum(
            sum(v for v in contas.values())
            for contas in grupos.values()
        )

    @property
    def total_receitas(self) -> float:
        return self.total_secao("1.") + self.ar

    @property
    def total_custos(self) -> float:
        return self.total_secao("2.")

    @property
    def total_despesas(self) -> float:
        return self.total_secao("3.") + self.ad

    @property
    def total_impostos(self) -> float:
        return self.total_secao("4.")

    @property
    def resultado_liquido(self) -> float:
        return (
            self.total_receitas
            + self.total_custos
            + self.total_despesas
            + self.total_impostos
        )

    @property
    def saldo_final(self) -> float:
        return self.saldo_anterior + self.saldo_banco + self.resultado_liquido


def calcular_dfc(
    plano_df: pd.DataFrame,
    ar: float = 0.0,
    ad: float = 0.0,
    saldo_anterior: float = 0.0,
    saldo_banco: float = 0.0,
    saldo_aplicacao: float = 0.0,
    saldo_caixa: float = 0.0,
) -> LinhasDFC:
    """
    Recebe o DataFrame do PlanoDeContas (colunas: codigo, descricao, valor)
    e devolve a estrutura DFC com valores assinados.
    """
    dfc = LinhasDFC(
        ar=ar, ad=ad,
        saldo_anterior=saldo_anterior,
        saldo_banco=saldo_banco,
        saldo_aplicacao=saldo_aplicacao,
        saldo_caixa=saldo_caixa,
    )

    for _, row in plano_df.iterrows():
        codigo = str(row["codigo"]).strip()
        valor  = float(row.get("valor", 0) or 0)

        sec = _secao(codigo)
        grp = _grupo(codigo)
        if not sec or not grp:
            continue

        sinal = SECOES.get(sec, {}).get("sinal", 1)
        valor_signed = sinal * valor

        dfc.dados.setdefault(sec, {}).setdefault(grp, {})[codigo] = valor_signed

    return dfc


def dfc_para_dataframe(dfc: LinhasDFC) -> pd.DataFrame:
    """
    Converte LinhasDFC em DataFrame tabular para exibição.
    Colunas: nivel, codigo, descricao, valor.
    """
    rows = []

    for sec_prefix, sec_info in SECOES.items():
        sec_total = dfc.total_secao(sec_prefix)

        # Ajuste especial de receita/despesa
        if sec_prefix == "1.":
            sec_total += dfc.ar
        if sec_prefix == "3.":
            sec_total += dfc.ad

        rows.append({
            "nivel": "secao",
            "codigo": sec_prefix,
            "descricao": sec_info["label"],
            "valor": sec_total,
        })

        grupos_da_secao = {k: v for k, v in GRUPOS.items() if k.startswith(sec_prefix[0])}
        for grp_prefix, grp_label in grupos_da_secao.items():
            contas = dfc.dados.get(sec_prefix, {}).get(grp_prefix, {})
            grp_total = sum(contas.values())
            if grp_total == 0 and not contas:
                continue

            rows.append({
                "nivel": "grupo",
                "codigo": grp_prefix,
                "descricao": grp_label,
                "valor": grp_total,
            })

            for cod, val in sorted(contas.items()):
                rows.append({
                    "nivel": "conta",
                    "codigo": cod,
                    "descricao": "",  # preenchido pelo caller se quiser
                    "valor": val,
                })

        # Ajustes manuais inline
        if sec_prefix == "1." and dfc.ar != 0:
            rows.append({"nivel": "ajuste", "codigo": "AR",
                         "descricao": "AJUSTE RECEITA", "valor": dfc.ar})
        if sec_prefix == "3." and dfc.ad != 0:
            rows.append({"nivel": "ajuste", "codigo": "AD",
                         "descricao": "AJUSTE DESPESA", "valor": dfc.ad})

    return pd.DataFrame(rows)
