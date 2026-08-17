"""Pydantic data models for the logitaxAgent system."""

from src.models.auditoria import RegistroAuditoria
from src.models.erro import CampoInvalido, ErroEstruturado
from src.models.estado import MAX_TENTATIVAS_RECLASSIFICACAO, AgentState
from src.models.operacao import (
    ANO_MAXIMO,
    ANO_MINIMO,
    UFS_VALIDAS,
    VALOR_FRETE_MAXIMO,
    VALOR_FRETE_MINIMO,
    OperacaoFrete,
)
from src.models.resultado import ResultadoAno, ResultadoConsolidado
from src.models.tabela_transicao import TabelaTransicaoResponse

__all__ = [
    # operacao.py
    "OperacaoFrete",
    "UFS_VALIDAS",
    "ANO_MINIMO",
    "ANO_MAXIMO",
    "VALOR_FRETE_MINIMO",
    "VALOR_FRETE_MAXIMO",
    # resultado.py
    "ResultadoAno",
    "ResultadoConsolidado",
    # estado.py
    "AgentState",
    "MAX_TENTATIVAS_RECLASSIFICACAO",
    # auditoria.py
    "RegistroAuditoria",
    # erro.py
    "ErroEstruturado",
    "CampoInvalido",
    # tabela_transicao.py
    "TabelaTransicaoResponse",
]
