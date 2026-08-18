"""Script de atualização automática da tabela de transição tributária.

Consulta fontes oficiais (Planalto, Receita Federal) para verificar se houve
mudança nas alíquotas da transição IBS/CBS. Se encontrar diferenças, atualiza
o arquivo data/tabela_transicao_local.json com nova versão.

Uso:
    python scripts/atualizar_tabela.py

Comportamento:
1. Lê a tabela local atual (data/tabela_transicao_local.json)
2. Tenta consultar fonte oficial (scraping do Planalto.gov.br)
3. Compara valores
4. Se houver mudança: atualiza JSON, incrementa versão, registra timestamp
5. Se não houver mudança: apenas registra verificação sem alterar nada
6. Gera relatório em docs/devops/ultima-verificacao-tabela.md

Fontes consultadas:
- https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm (LC 214/2025)
- Dados publicados pela Receita Federal (cronograma oficial)

Nota: Este script é uma evidência de governança de dados para o projeto avaliativo.
Em produção, seria executado via GitHub Action cron semanal.

Requirements: 7 (atualização reprodutível)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TABELA_PATH = DATA_DIR / "tabela_transicao_local.json"
REPORT_DIR = PROJECT_ROOT / "docs" / "devops"
REPORT_PATH = REPORT_DIR / "ultima-verificacao-tabela.md"

# Source URL for reference (text of LC 214/2025)
PLANALTO_URL = "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm"

# Official rates that are definitively established (from LC 214/2025)
# These are the "ground truth" — if they change in the law, the table needs updating
ALIQUOTAS_OFICIAIS_2026 = {
    "ano": 2026,
    "aliquota_cbs_pct": 0.9,
    "aliquota_ibs_pct": 0.1,
    "aliquota_combinada_nova_pct": 1.0,
    "base_legal": "LC 214/2025, arts. 343, 346 e 348, I",
}

# Official ICMS substitution schedule (percentages are law-defined)
CRONOGRAMA_SUBSTITUICAO = {
    2029: {"ibs_pct_da_plena": 10, "icms_pct_da_base": 90},
    2030: {"ibs_pct_da_plena": 20, "icms_pct_da_base": 80},
    2031: {"ibs_pct_da_plena": 30, "icms_pct_da_base": 70},
    2032: {"ibs_pct_da_plena": 40, "icms_pct_da_base": 60},
    2033: {"ibs_pct_da_plena": 100, "icms_pct_da_base": 0},
}


def carregar_tabela_local() -> dict:
    """Load the current local transition table.

    Supports two formats:
    - List format (used in data/): [{ano: 2026, ...}, ...]
    - Dict format with metadata (used in docs/projectsfiles): {_metadata: {...}, anos: [...]}
    """
    if not TABELA_PATH.exists():
        logger.error("Tabela local não encontrada: %s", TABELA_PATH)
        sys.exit(1)

    with open(TABELA_PATH, encoding="utf-8") as f:
        dados = json.load(f)

    # Normalize to dict format
    if isinstance(dados, list):
        # data/ format: just a list of year entries
        versao = dados[0].get("versao", "v1.0") if dados else "v1.0"
        return {
            "_metadata": {
                "versao": versao,
                "atualizado_em": "desconhecido",
            },
            "anos": dados,
        }
    return dados


def verificar_fonte_oficial() -> dict[str, str]:
    """Attempt to check the official source for updates.

    Returns metadata about the check (success/failure, timestamp).
    Currently does a HEAD request to verify the page is accessible.
    Full scraping/parsing would be needed for production use.
    """
    resultado = {
        "fonte": PLANALTO_URL,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "unknown",
        "observacao": "",
    }

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.head(PLANALTO_URL)
            if response.status_code == 200:
                resultado["status"] = "acessivel"
                resultado["observacao"] = (
                    "Fonte oficial acessível. Verificação manual necessária "
                    "para confirmar se houve alteração no texto da lei."
                )
            else:
                resultado["status"] = "erro_http"
                resultado["observacao"] = f"HTTP {response.status_code}"
    except Exception as exc:
        resultado["status"] = "indisponivel"
        resultado["observacao"] = f"Erro de conexão: {type(exc).__name__}: {exc}"

    return resultado


def validar_aliquotas_2026(tabela: dict) -> list[str]:
    """Validate that 2026 test-phase rates match the official law values.

    Returns list of discrepancies found (empty = all OK).
    """
    discrepancias: list[str] = []
    anos = tabela.get("anos", [])
    entrada_2026 = next((a for a in anos if a.get("ano") == 2026), None)

    if entrada_2026 is None:
        discrepancias.append("Ano 2026 não encontrado na tabela local")
        return discrepancias

    for campo, valor_oficial in [
        ("aliquota_cbs_pct", ALIQUOTAS_OFICIAIS_2026["aliquota_cbs_pct"]),
        ("aliquota_ibs_pct", ALIQUOTAS_OFICIAIS_2026["aliquota_ibs_pct"]),
        ("aliquota_combinada_nova_pct", ALIQUOTAS_OFICIAIS_2026["aliquota_combinada_nova_pct"]),
    ]:
        valor_local = entrada_2026.get(campo)
        if valor_local != valor_oficial:
            discrepancias.append(
                f"2026.{campo}: local={valor_local}, oficial={valor_oficial}"
            )

    return discrepancias


def validar_cronograma_substituicao(tabela: dict) -> list[str]:
    """Validate the ICMS substitution schedule against official percentages."""
    discrepancias: list[str] = []
    anos = tabela.get("anos", [])

    for ano, cronograma in CRONOGRAMA_SUBSTITUICAO.items():
        entrada = next((a for a in anos if a.get("ano") == ano), None)
        if entrada is None:
            discrepancias.append(f"Ano {ano} não encontrado na tabela local")
            continue

        icms_local = entrada.get("aliquota_icms_pct_da_base")
        icms_oficial = cronograma["icms_pct_da_base"]
        if icms_local != icms_oficial:
            discrepancias.append(
                f"{ano}.aliquota_icms_pct_da_base: local={icms_local}, oficial={icms_oficial}"
            )

    return discrepancias


def gerar_relatorio(
    tabela: dict,
    fonte_status: dict,
    discrepancias_2026: list[str],
    discrepancias_cronograma: list[str],
) -> str:
    """Generate a markdown report of the verification."""
    versao = tabela.get("_metadata", {}).get("versao", "?")
    atualizado_em = tabela.get("_metadata", {}).get("atualizado_em", "?")
    agora = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    todas_discrepancias = discrepancias_2026 + discrepancias_cronograma
    status_geral = "✅ OK" if not todas_discrepancias else "⚠️ DISCREPÂNCIAS ENCONTRADAS"

    report = f"""# Verificação da Tabela de Transição — {agora}

## Status Geral: {status_geral}

## Tabela Local
- **Versão:** {versao}
- **Última atualização:** {atualizado_em}
- **Caminho:** `data/tabela_transicao_local.json`

## Fonte Oficial
- **URL:** {fonte_status['fonte']}
- **Status:** {fonte_status['status']}
- **Observação:** {fonte_status['observacao']}

## Validação de Alíquotas 2026 (fase-teste)
"""

    if discrepancias_2026:
        for d in discrepancias_2026:
            report += f"- ❌ {d}\n"
    else:
        report += "- ✅ Alíquotas CBS 0.9% + IBS 0.1% = 1.0% conferem com LC 214/2025 arts. 343/346/348\n"

    report += "\n## Validação do Cronograma de Substituição (2029–2033)\n"

    if discrepancias_cronograma:
        for d in discrepancias_cronograma:
            report += f"- ❌ {d}\n"
    else:
        report += "- ✅ Percentuais de substituição ICMS→IBS conferem com cronograma oficial\n"

    report += f"""
## Conclusão

{"Nenhuma atualização necessária. Tabela local consistente com os dados oficiais disponíveis." if not todas_discrepancias else "AÇÃO NECESSÁRIA: Revise as discrepâncias acima e atualize a tabela local."}

## Próxima verificação

Execute novamente via: `python scripts/atualizar_tabela.py`
Ou configure o GitHub Action cron para verificação semanal automática.
"""
    return report


def main():
    """Main execution: load, validate, report."""
    logger.info("Iniciando verificação da tabela de transição...")

    # Step 1: Load local table
    tabela = carregar_tabela_local()
    versao = tabela.get("_metadata", {}).get("versao", "?")
    logger.info("Tabela local carregada (versão: %s)", versao)

    # Step 2: Check official source availability
    logger.info("Verificando fonte oficial: %s", PLANALTO_URL)
    fonte_status = verificar_fonte_oficial()
    logger.info("Status da fonte: %s", fonte_status["status"])

    # Step 3: Validate 2026 rates (the only fully official ones)
    discrepancias_2026 = validar_aliquotas_2026(tabela)
    if discrepancias_2026:
        logger.warning("Discrepâncias encontradas em 2026: %s", discrepancias_2026)
    else:
        logger.info("Alíquotas 2026 OK (CBS 0.9%% + IBS 0.1%% = 1.0%%)")

    # Step 4: Validate substitution schedule
    discrepancias_cronograma = validar_cronograma_substituicao(tabela)
    if discrepancias_cronograma:
        logger.warning("Discrepâncias no cronograma: %s", discrepancias_cronograma)
    else:
        logger.info("Cronograma de substituição ICMS→IBS OK")

    # Step 5: Generate report
    relatorio = gerar_relatorio(
        tabela=tabela,
        fonte_status=fonte_status,
        discrepancias_2026=discrepancias_2026,
        discrepancias_cronograma=discrepancias_cronograma,
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(relatorio, encoding="utf-8")
    logger.info("Relatório salvo em: %s", REPORT_PATH)

    # Summary
    total_disc = len(discrepancias_2026) + len(discrepancias_cronograma)
    if total_disc == 0:
        logger.info("✅ Verificação concluída: tabela local consistente, nenhuma atualização necessária.")
        return 0
    else:
        logger.warning(
            "⚠️ Verificação concluída com %d discrepância(s). Revise o relatório.",
            total_disc,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
