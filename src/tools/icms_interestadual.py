"""Lookup de alíquota ICMS interestadual por par de UFs (CONFAZ).

Regras baseadas na Resolução do Senado Federal 22/1989:
- 12% entre estados do Sul/Sudeste
- 7% de Sul/Sudeste para N/NE/CO/ES
- 12% de N/NE/CO/ES para qualquer destino
- Intraestadual: alíquota interna do estado

Fallback: 12% se par de UFs não encontrado.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ICMS_INTERESTADUAL_PATH = DATA_DIR / "icms_interestadual.json"

# Default fallback rate
ICMS_DEFAULT_PCT = 12.0

# Cache loaded data
_dados_cache: dict | None = None


def _carregar_dados() -> dict:
    """Load ICMS interestadual data from JSON (cached)."""
    global _dados_cache
    if _dados_cache is None:
        with open(ICMS_INTERESTADUAL_PATH, encoding="utf-8") as f:
            _dados_cache = json.load(f)
    return _dados_cache


def consultar_icms_interestadual(uf_origem: str, uf_destino: str) -> float:
    """Look up ICMS interestadual rate for a given origin-destination UF pair.

    Args:
        uf_origem: Origin UF code (2 letters, uppercase).
        uf_destino: Destination UF code (2 letters, uppercase).

    Returns:
        ICMS rate in percentage (e.g., 7.0 or 12.0).
    """
    uf_origem = uf_origem.upper()
    uf_destino = uf_destino.upper()

    # Intraestadual
    if uf_origem == uf_destino:
        dados = _carregar_dados()
        internas = dados.get("aliquotas_internas", {})
        return internas.get(uf_origem, 18.0)

    # Interestadual
    dados = _carregar_dados()
    regioes = dados.get("regioes", {})
    regras = dados.get("regras_aliquota", {})

    sul_sudeste = set(regioes.get("sul_sudeste", []))

    origem_sul_sudeste = uf_origem in sul_sudeste
    destino_sul_sudeste = uf_destino in sul_sudeste

    if origem_sul_sudeste and destino_sul_sudeste:
        return regras.get("sul_sudeste_para_sul_sudeste", 12.0)
    elif origem_sul_sudeste and not destino_sul_sudeste:
        return regras.get("sul_sudeste_para_norte_nordeste_co_es", 7.0)
    else:
        return regras.get("norte_nordeste_co_es_para_qualquer", 12.0)
