"""
Utilitários compartilhados — formatação e helpers gerais.
"""


def fmt_br(v: float) -> str:
    """Formata valor em Real no padrão brasileiro com centavos.

    Exemplo: 71028.99 → 'R$ 71.028,99'
    """
    v = round(v, 2) or 0.0  # elimina -0.0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_br_kpi(v: float) -> str:
    """Formata valor em Real sem centavos para cards de KPI.

    Exemplo: 71028.99 → 'R$ 71.029'
    """
    return f"R$ {abs(v):,.0f}".replace(",", ".")
