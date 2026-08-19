"""Script de ingestão de trechos legislativos no índice vetorial ChromaDB.

Indexa excertos da LC 214/2025, EC 132/2023 e Notas Técnicas CT-e
para uso pelo módulo RAG do logitaxAgent.

Cada chunk é armazenado com metadata:
  - source_law: identificador da lei/norma
  - article_number: número do artigo ou seção
  - applicable_year_range: faixa de anos aplicável (ex: "2026-2033")

Uso:
    python scripts/run_ingestao.py [--chromadb-path PATH]
"""

import argparse
import logging
import os
import sys

# Adicionar raiz do projeto ao path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("ingestao")

# Nome da coleção ChromaDB
COLLECTION_NAME = "legislacao_tributaria"

# Chunks legislativos representativos
CHUNKS: list[dict] = [
    # --- LC 214/2025 - IBS e CBS ---
    {
        "id": "lc214-art343",
        "document": (
            "Art. 343, LC 214/2025: Durante o período de teste em 2026, "
            "a alíquota da CBS será de 0,9% e a do IBS será de 0,1%, "
            "totalizando 1,0% de alíquota combinada sobre o valor da operação. "
            "O objetivo é validar o sistema de arrecadação sem impacto fiscal significativo."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 343",
            "applicable_year_range": "2026-2026",
        },
    },
    {
        "id": "lc214-art344",
        "document": (
            "Art. 344, LC 214/2025: A partir de 2027, a CBS substituirá integralmente "
            "o PIS e a COFINS, com alíquota de referência de 8,8%. O IBS será cobrado "
            "em paralelo ao ICMS durante o período de transição, com alíquota inicial "
            "residual de 0,1% em 2027-2028."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 344",
            "applicable_year_range": "2027-2028",
        },
    },
    {
        "id": "lc214-art346",
        "document": (
            "Art. 346, LC 214/2025: O IBS será implementado de forma progressiva. "
            "A partir de 2029, o ICMS será reduzido em 10% ao ano (90% em 2029, "
            "80% em 2030, 70% em 2031, 60% em 2032) enquanto o IBS aumenta "
            "proporcionalmente para compensar a perda de arrecadação."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 346",
            "applicable_year_range": "2029-2032",
        },
    },
    {
        "id": "lc214-art348",
        "document": (
            "Art. 348, LC 214/2025: Em 2033, o ICMS será completamente extinto "
            "e o IBS assumirá integralmente a tributação estadual/municipal sobre "
            "bens e serviços, incluindo operações de transporte de cargas. "
            "A alíquota combinada (CBS + IBS) em regime pleno é de 27,9%."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 348",
            "applicable_year_range": "2033-2033",
        },
    },
    {
        "id": "lc214-art156",
        "document": (
            "Art. 156, LC 214/2025: O regime não-cumulativo do IBS e da CBS "
            "assegura ao contribuinte do regime regular (Lucro Real ou Lucro Presumido) "
            "o direito a créditos plenos sobre insumos utilizados na prestação de "
            "serviços de transporte, incluindo combustíveis, manutenção e pedágios."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 156",
            "applicable_year_range": "2026-2033",
        },
    },
    {
        "id": "lc214-art200",
        "document": (
            "Art. 200, LC 214/2025: Os optantes pelo Simples Nacional não terão "
            "direito a créditos de IBS/CBS na modalidade não-cumulativa. "
            "O cálculo do tributo para empresas do Simples considera a alíquota "
            "cheia sem abatimento de créditos sobre insumos."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 200",
            "applicable_year_range": "2026-2033",
        },
    },
    {
        "id": "lc214-art350",
        "document": (
            "Art. 350, LC 214/2025: Durante a transição (2027-2032), o ICMS "
            "interestadual permanece com alíquota base de 12% para operações "
            "de transporte rodoviário de cargas entre estados. A redução gradual "
            "aplica-se sobre essa base conforme o cronograma do art. 346."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 350",
            "applicable_year_range": "2027-2032",
        },
    },
    # --- EC 132/2023 - Emenda Constitucional da Reforma ---
    {
        "id": "ec132-art1",
        "document": (
            "Art. 1º, EC 132/2023: Institui o Imposto sobre Bens e Serviços (IBS) "
            "e a Contribuição sobre Bens e Serviços (CBS), em substituição ao ICMS, "
            "ISS, PIS, COFINS e IPI. A transição ocorrerá entre 2026 e 2033, "
            "com período de teste em 2026."
        ),
        "metadata": {
            "source_law": "EC 132/2023",
            "article_number": "art. 1",
            "applicable_year_range": "2026-2033",
        },
    },
    {
        "id": "ec132-art3",
        "document": (
            "Art. 3º, EC 132/2023: O IBS e a CBS incidirão sobre todas as operações "
            "com bens e serviços, incluindo prestações de serviço de transporte "
            "interestadual e intermunicipal. A base de cálculo é o valor da operação, "
            "sem inclusão do próprio tributo na base (cálculo por fora)."
        ),
        "metadata": {
            "source_law": "EC 132/2023",
            "article_number": "art. 3",
            "applicable_year_range": "2026-2033",
        },
    },
    {
        "id": "ec132-art9",
        "document": (
            "Art. 9º, EC 132/2023: As alíquotas de referência do IBS e da CBS "
            "serão fixadas de modo a manter a carga tributária global equivalente "
            "à vigente no período de referência. O Comitê Gestor e a Receita Federal "
            "revisarão anualmente as alíquotas de referência."
        ),
        "metadata": {
            "source_law": "EC 132/2023",
            "article_number": "art. 9",
            "applicable_year_range": "2026-2033",
        },
    },
    # --- Notas Técnicas CT-e ---
    {
        "id": "nt-cte-2025001-secao3",
        "document": (
            "NT 2025.001, Seção 3 - CT-e: A partir de 2026, o Conhecimento de "
            "Transporte eletrônico (CT-e) deverá informar o campo cClassTrib "
            "(Código de Classificação Tributária) indicando se a operação está sujeita "
            "ao regime de teste IBS/CBS ou permanece exclusivamente no regime atual."
        ),
        "metadata": {
            "source_law": "NT CT-e 2025.001",
            "article_number": "seção 3",
            "applicable_year_range": "2026-2033",
        },
    },
    {
        "id": "nt-cte-2025001-secao5",
        "document": (
            "NT 2025.001, Seção 5 - CT-e: O campo cClassTrib no CT-e deve refletir "
            "o regime tributário do transportador: 01 para Lucro Real com créditos "
            "plenos, 02 para Lucro Presumido, e 03 para Simples Nacional sem "
            "creditamento. Essa classificação impacta diretamente o cálculo do frete."
        ),
        "metadata": {
            "source_law": "NT CT-e 2025.001",
            "article_number": "seção 5",
            "applicable_year_range": "2026-2033",
        },
    },
    {
        "id": "nt-cte-2025002-secao2",
        "document": (
            "NT 2025.002, Seção 2 - CT-e: Durante o período de transição (2029-2032), "
            "o CT-e deverá discriminar separadamente as parcelas de ICMS residual "
            "e IBS/CBS, permitindo ao tomador do serviço de transporte identificar "
            "as alíquotas aplicáveis e exercer o direito a crédito conforme seu regime."
        ),
        "metadata": {
            "source_law": "NT CT-e 2025.002",
            "article_number": "seção 2",
            "applicable_year_range": "2029-2032",
        },
    },
    {
        "id": "nt-cte-2025002-secao4",
        "document": (
            "NT 2025.002, Seção 4 - CT-e: Em 2033, com a extinção do ICMS, o CT-e "
            "passará a informar exclusivamente os campos referentes ao IBS e CBS. "
            "O campo de ICMS será descontinuado e substituído pelo campo de IBS "
            "estadual, mantendo rastreabilidade fiscal completa."
        ),
        "metadata": {
            "source_law": "NT CT-e 2025.002",
            "article_number": "seção 4",
            "applicable_year_range": "2033-2033",
        },
    },
    {
        "id": "lc214-art352",
        "document": (
            "Art. 352, LC 214/2025: O delta percentual entre a carga tributária "
            "do regime atual e do regime novo pode variar significativamente conforme "
            "o ano de referência. Em 2026 (fase de teste), espera-se redução expressiva "
            "da carga; a partir de 2029, a carga tende a se aproximar do patamar atual "
            "conforme o ICMS é gradualmente substituído pelo IBS."
        ),
        "metadata": {
            "source_law": "LC 214/2025",
            "article_number": "art. 352",
            "applicable_year_range": "2026-2033",
        },
    },
]


def get_chromadb_path(args_path: str | None = None) -> str:
    """Determina o path do ChromaDB a partir de args, env ou default."""
    if args_path:
        return args_path
    return os.environ.get("CHROMADB_PATH", "./data/chromadb")


def run_ingestao(chromadb_path: str) -> dict:
    """Executa a ingestão de chunks legislativos no ChromaDB.

    Args:
        chromadb_path: Caminho para o diretório persistente do ChromaDB.

    Returns:
        Dicionário com estatísticas da ingestão:
            - total_chunks: número de chunks indexados com sucesso
            - errors: lista de erros de parsing encontrados
    """
    stats = {"total_chunks": 0, "errors": []}

    logger.info("Iniciando ingestão de trechos legislativos")
    logger.info("ChromaDB path: %s", chromadb_path)

    # Inicializar client persistente
    try:
        client = chromadb.PersistentClient(path=chromadb_path)
        logger.info("ChromaDB client inicializado com sucesso")
    except Exception as e:
        error_msg = f"Erro ao inicializar ChromaDB client: {e}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        return stats

    # Criar/obter coleção (idempotente via get_or_create)
    try:
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Trechos legislativos sobre IBS/CBS e transporte de cargas"},
        )
        logger.info(
            "Coleção '%s' pronta (documentos existentes: %d)",
            COLLECTION_NAME,
            collection.count(),
        )
    except Exception as e:
        error_msg = f"Erro ao criar/obter coleção: {e}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        return stats

    # Indexar chunks usando upsert (idempotente)
    ids = []
    documents = []
    metadatas = []

    for chunk in CHUNKS:
        try:
            ids.append(chunk["id"])
            documents.append(chunk["document"])
            metadatas.append(chunk["metadata"])
        except (KeyError, TypeError) as e:
            error_msg = f"Erro de parsing no chunk '{chunk.get('id', 'unknown')}': {e}"
            logger.warning(error_msg)
            stats["errors"].append(error_msg)

    # Upsert em batch (idempotente - re-execuções não duplicam)
    if ids:
        try:
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            stats["total_chunks"] = len(ids)
            logger.info("Chunks indexados com sucesso: %d", stats["total_chunks"])
        except Exception as e:
            error_msg = f"Erro ao inserir chunks no ChromaDB: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

    # Verificar contagem final
    final_count = collection.count()
    logger.info("Total de documentos na coleção '%s': %d", COLLECTION_NAME, final_count)

    # Resumo
    if stats["errors"]:
        logger.warning("Ingestão concluída com %d erro(s)", len(stats["errors"]))
        for err in stats["errors"]:
            logger.warning("  - %s", err)
    else:
        logger.info("Ingestão concluída sem erros")

    return stats


def main():
    """Ponto de entrada do script de ingestão."""
    parser = argparse.ArgumentParser(
        description="Indexar trechos legislativos no ChromaDB para RAG"
    )
    parser.add_argument(
        "--chromadb-path",
        type=str,
        default=None,
        help="Caminho para o diretório persistente do ChromaDB "
        "(default: CHROMADB_PATH env ou ./data/chromadb)",
    )
    args = parser.parse_args()

    chromadb_path = get_chromadb_path(args.chromadb_path)
    stats = run_ingestao(chromadb_path)

    # Exit code baseado no resultado
    if stats["errors"] and stats["total_chunks"] == 0:
        logger.error("Nenhum chunk foi indexado. Abortando com erro.")
        sys.exit(1)

    logger.info(
        "Resultado final: %d chunks indexados, %d erros",
        stats["total_chunks"],
        len(stats["errors"]),
    )


if __name__ == "__main__":
    main()
