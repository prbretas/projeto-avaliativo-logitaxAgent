"""Node: generate_justification — LLM generates natural language justification citing legislation.

This node composes a prompt with RAG excerpts (trechos_rag from retrieve_context) and
tax calculation results (resultados_por_ano from fan-out/fan-in), calls the LLM, and
validates that any tax rates cited in the generated text match the rates from Tool_Transicao.

Validation logic:
1. Extract percentages mentioned in the generated justification text.
2. Cross-reference them against the known rates from the simulation results.
3. On mismatch: discard the justification, log the integrity event, and retry up to 2x.
4. If all retries fail: escalate to human_review by setting revisao_manual=True.

The LLM endpoint is configured via LLM_MODEL_NAME and LLM_ENDPOINT env variables.

Requirements: 7.2, 7.4, 7.5
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import httpx

from src.tools.client_transicao import consultar_tabela_transicao

logger = logging.getLogger("logitaxAgent.justificativa")

# LLM Configuration from environment
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "https://api.openai.com/v1")

# Maximum retries for justification generation on rate mismatch
MAX_JUSTIFICATION_RETRIES = 2

# Timeout for LLM API calls (seconds)
LLM_TIMEOUT_SECONDS = 30.0

# Regex to find percentage values in generated text (e.g., "0.9%", "12.0%", "8.8%")
_RATE_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _build_prompt(
    trechos_rag: list[str],
    resultados_por_ano: list[dict[str, Any]],
    operacao: dict[str, Any],
) -> str:
    """Compose the system + user prompt for justification generation.

    The prompt includes:
    - System instructions (role, output format, constraints)
    - RAG excerpts from legislation
    - Calculation results per year
    - Operation context

    Args:
        trechos_rag: Legislative excerpts retrieved from ChromaDB.
        resultados_por_ano: List of ResultadoAno dicts with tax calculations.
        operacao: OperacaoFrete data (modal, UFs, regime, valor_frete, etc.).

    Returns:
        Formatted prompt string for the LLM.
    """
    # Format RAG excerpts
    if trechos_rag:
        trechos_formatados = "\n\n".join(
            f"[Trecho {i + 1}]: {trecho}" for i, trecho in enumerate(trechos_rag)
        )
    else:
        trechos_formatados = "[Nenhum trecho legislativo encontrado para este cenário]"

    # Format calculation results
    resultados_formatados = json.dumps(resultados_por_ano, indent=2, ensure_ascii=False)

    # Extract operation details
    modal = (
        operacao.get("modal", "N/A")
        if isinstance(operacao, dict)
        else getattr(operacao, "modal", "N/A")
    )
    origem_uf = (
        operacao.get("origem_uf", "N/A")
        if isinstance(operacao, dict)
        else getattr(operacao, "origem_uf", "N/A")
    )
    destino_uf = (
        operacao.get("destino_uf", "N/A")
        if isinstance(operacao, dict)
        else getattr(operacao, "destino_uf", "N/A")
    )
    regime = (
        operacao.get("regime_tributario", "N/A")
        if isinstance(operacao, dict)
        else getattr(operacao, "regime_tributario", "N/A")
    )
    valor_frete = (
        operacao.get("valor_frete", 0)
        if isinstance(operacao, dict)
        else getattr(operacao, "valor_frete", 0)
    )

    prompt = f"""Você é um analista tributário especializado na Reforma Tributária brasileira (LC 214/2025).

## REGRAS OBRIGATÓRIAS

1. Gere uma justificativa técnica em português brasileiro sobre o impacto da transição IBS/CBS no frete.
2. Cite APENAS as alíquotas exatas que constam nos resultados de cálculo fornecidos abaixo.
3. Para cada ano simulado, mencione as alíquotas CBS e IBS aplicadas (conforme Tabela de Transição).
4. Cite artigos da legislação SOMENTE se estiverem nos trechos RAG fornecidos.
5. NÃO invente artigos, números de lei ou alíquotas que não estejam nos dados fornecidos.
6. A justificativa deve ser clara, concisa e auditável.
7. Formato de saída: texto corrido com parágrafos, citando fontes entre parênteses.

## CONTEXTO DA OPERAÇÃO

- Modal: {modal}
- Origem UF: {origem_uf}
- Destino UF: {destino_uf}
- Regime Tributário: {regime}
- Valor do Frete: R$ {valor_frete:,.2f}

## TRECHOS LEGISLATIVOS (RAG)

{trechos_formatados}

## RESULTADOS DE CÁLCULO POR ANO

{resultados_formatados}

## INSTRUÇÃO FINAL

Com base nos trechos legislativos e resultados acima, elabore a justificativa técnica explicando o impacto da transição tributária IBS/CBS sobre esta operação de frete. Mencione as alíquotas exatas de cada ano simulado e cite os artigos relevantes da legislação quando disponíveis nos trechos RAG."""

    return prompt


def _extract_rates_from_text(text: str) -> set[float]:
    """Extract all percentage values mentioned in the generated justification.

    Parses patterns like "0.9%", "8,8%", "12.0%" from the text.

    Args:
        text: The generated justification text.

    Returns:
        Set of float values representing percentages found in the text.
    """
    rates: set[float] = set()
    matches = _RATE_PATTERN.findall(text)
    for match in matches:
        # Handle both comma and dot as decimal separator
        normalized = match.replace(",", ".")
        try:
            rate = float(normalized)
            rates.add(rate)
        except ValueError:
            continue
    return rates


def _get_valid_rates_from_results(resultados_por_ano: list[dict[str, Any]]) -> set[float]:
    """Collect all valid tax rates from the calculation results and known constants.

    Includes:
    - CBS rate, IBS rate, ICMS phase-out %, combined new rate per year
    - Known Regime_Atual constants: PIS 1.65%, COFINS 7.6%, ICMS 12.0%, total 21.25%
    - Delta percentual values

    Args:
        resultados_por_ano: List of result dicts with year-specific data.

    Returns:
        Set of all valid rate floats that may be cited in the justification.
    """
    valid_rates: set[float] = set()

    # Regime_Atual known constants
    valid_rates.update({1.65, 7.6, 12.0, 21.25, 9.25})

    # Rates from each year's results
    for resultado in resultados_por_ano:
        if isinstance(resultado, dict):
            delta = resultado.get("delta_percentual")
            if delta is not None:
                valid_rates.add(abs(round(float(delta), 2)))
                valid_rates.add(round(float(delta), 2))
        else:
            # Pydantic model
            delta = getattr(resultado, "delta_percentual", None)
            if delta is not None:
                valid_rates.add(abs(round(float(delta), 2)))
                valid_rates.add(round(float(delta), 2))

    return valid_rates


async def _get_tool_rates_for_years(
    anos: list[int],
    uf_origem: str,
    uf_destino: str,
    regime: str,
) -> set[float]:
    """Fetch rates from Tool_Transicao for validation against the justification text.

    Args:
        anos: List of years to fetch rates for.
        uf_origem: Origin UF code.
        uf_destino: Destination UF code.
        regime: Tax regime.

    Returns:
        Set of valid rate floats from Tool_Transicao.
    """
    valid_rates: set[float] = set()

    for ano in anos:
        try:
            result = await consultar_tabela_transicao(
                ano=ano,
                uf_origem=uf_origem,
                uf_destino=uf_destino,
                regime=regime,
            )
            tabela = result.dados
            valid_rates.add(tabela.aliquota_cbs_pct)
            valid_rates.add(tabela.aliquota_ibs_pct)
            valid_rates.add(tabela.aliquota_icms_pct_da_base)
            valid_rates.add(tabela.aliquota_combinada_nova_pct)
            # Also add computed ICMS effective rate
            icms_efetivo = round(12.0 * tabela.aliquota_icms_pct_da_base / 100.0, 2)
            valid_rates.add(icms_efetivo)
        except Exception as exc:
            logger.warning("Failed to fetch tool rates for year %d: %s", ano, str(exc))

    return valid_rates


def _validate_rates(
    justification_text: str,
    valid_rates: set[float],
) -> tuple[bool, list[str]]:
    """Validate that rates cited in justification match Tool_Transicao rates.

    Checks every percentage value in the generated text against the set of
    known valid rates. Reports mismatches.

    Args:
        justification_text: The generated justification text from LLM.
        valid_rates: Set of all valid rate values that can be cited.

    Returns:
        Tuple of (is_valid, list of mismatch descriptions).
    """
    cited_rates = _extract_rates_from_text(justification_text)
    mismatches: list[str] = []

    for rate in cited_rates:
        # Check if the cited rate matches any valid rate (with tolerance for rounding)
        if not any(abs(rate - valid) < 0.01 for valid in valid_rates):
            mismatches.append(f"Rate {rate}% not found in valid tool rates")

    is_valid = len(mismatches) == 0
    return is_valid, mismatches


async def _call_llm(prompt: str) -> str:
    """Call the LLM API to generate the justification text.

    Uses the OpenAI-compatible chat completions endpoint configured via
    LLM_MODEL_NAME and LLM_ENDPOINT environment variables.

    Args:
        prompt: The composed prompt string.

    Returns:
        The generated justification text from the LLM.

    Raises:
        httpx.HTTPStatusError: If the API returns an error status.
        httpx.TimeoutException: If the request exceeds LLM_TIMEOUT_SECONDS.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    url = f"{LLM_ENDPOINT}/chat/completions"

    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }
    # Only add auth header if a real API key is configured (not "ollama" or empty)
    if api_key and api_key.lower() != "ollama":
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um analista tributário especialista em Reforma Tributária "
                    "brasileira. Responda APENAS com a justificativa técnica solicitada, "
                    "sem preâmbulos ou explicações adicionais."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _gerar_comentario_agente(
    resultados_por_ano: list[dict[str, Any]],
    operacao: Any,
) -> str:
    """Generate an analytical comment about the simulation results.

    Creates a concise, actionable paragraph explaining:
    - Summary of impact (economy or increase)
    - Root cause (which tax component drives the change)
    - Practical recommendation
    - Warning if data is estimated (not official)

    This is deterministic (no LLM call) — uses calculation results directly.
    Max ~200 words, accessible language for freight managers.

    Args:
        resultados_por_ano: List of result dicts with year calculations.
        operacao: The freight operation (dict or Pydantic model).

    Returns:
        Analytical comment string.
    """
    if not resultados_por_ano:
        return "Nenhum resultado de simulação disponível para análise."

    # Extract operation details
    if isinstance(operacao, dict):
        regime = operacao.get("regime_tributario", "lucro_real")
        operacao.get("valor_frete", 0)
    else:
        regime = getattr(operacao, "regime_tributario", "lucro_real")
        getattr(operacao, "valor_frete", 0)

    # Analyze results
    partes: list[str] = []

    # Overall trend
    deltas = [
        r.get("delta_percentual", 0) if isinstance(r, dict) else getattr(r, "delta_percentual", 0)
        for r in resultados_por_ano
    ]
    media_delta = sum(deltas) / len(deltas) if deltas else 0

    if media_delta > 5:
        partes.append(
            f"A simulação indica um aumento médio de {abs(media_delta):.1f}% na carga "
            f"tributária ao longo do período de transição."
        )
    elif media_delta < -5:
        partes.append(
            f"A simulação indica uma redução média de {abs(media_delta):.1f}% na carga "
            f"tributária ao longo do período de transição."
        )
    else:
        partes.append(
            "A simulação indica variação moderada na carga tributária durante a transição."
        )

    # Year with biggest impact
    if len(deltas) > 1:
        max_idx = deltas.index(max(deltas, key=abs))
        resultado_max = resultados_por_ano[max_idx]
        ano_max = (
            resultado_max.get("ano")
            if isinstance(resultado_max, dict)
            else getattr(resultado_max, "ano", "?")
        )
        delta_max = deltas[max_idx]
        if delta_max > 0:
            partes.append(
                f"O maior impacto ocorre em {ano_max}, com aumento de {delta_max:.1f}% "
                f"— causado pela entrada plena do IBS substituindo o ICMS."
            )
        else:
            partes.append(
                f"A maior economia ocorre em {ano_max}, com redução de {abs(delta_max):.1f}%."
            )

    # Regime-specific advice
    if regime == "simples_nacional":
        partes.append(
            "Atenção: optantes do Simples Nacional não aproveitam créditos IBS/CBS. "
            "Avalie a migração para regime regular antes de 2029 se o volume de frete justificar."
        )
    elif media_delta > 10:
        partes.append(
            "Recomenda-se revisar contratos de frete com vigência após 2027, "
            "considerando cláusula de reajuste tributário."
        )

    # Warning about estimated data
    tem_estimativa = any(
        not (
            r.get("detalhe_regime_novo", {}).get("oficial", True)
            if isinstance(r, dict)
            else getattr(getattr(r, "detalhe_regime_novo", None), "oficial", True)
        )
        for r in resultados_por_ano
    )
    if tem_estimativa:
        partes.append(
            "Nota: algumas alíquotas utilizadas são projeções técnicas (CGIBS/MF), "
            "não valores oficiais. Resultados podem variar após resolução do Senado."
        )

    return " ".join(partes)


async def generate_justification(state: dict[str, Any]) -> dict[str, Any]:
    """Generate a natural language justification citing legislation via LLM.

    This is the main node function for the LangGraph StateGraph. It:
    1. Composes a prompt with RAG excerpts + calculation results
    2. Calls the LLM to generate justification
    3. Validates cited rates against Tool_Transicao
    4. On mismatch: discards, logs, retries up to 2x
    5. If all retries fail: escalates to human_review

    Args:
        state: Current AgentState dict. Expected keys:
            - trechos_rag: list[str] from retrieve_context
            - resultados_por_ano: list[ResultadoAno] from fan-out/fan-in
            - operacao: OperacaoFrete
            - thread_id: str

    Returns:
        Partial state update with:
            - justificativa: str (the validated justification text)
            - revisao_manual: bool (True if escalated due to repeated mismatch)
            - alertas: list[str] (any warnings added)
    """
    trechos_rag = state.get("trechos_rag", [])
    resultados_por_ano = state.get("resultados_por_ano", [])
    operacao = state.get("operacao")
    thread_id = state.get("thread_id", "unknown")
    alertas = list(state.get("alertas", []))

    # Convert ResultadoAno objects to dicts for prompt composition
    resultados_dicts = []
    for r in resultados_por_ano:
        if hasattr(r, "model_dump"):
            resultados_dicts.append(r.model_dump())
        elif isinstance(r, dict):
            resultados_dicts.append(r)
        else:
            resultados_dicts.append({"ano": getattr(r, "ano", "?")})

    # Extract operation fields
    if hasattr(operacao, "origem_uf"):
        uf_origem = operacao.origem_uf
        uf_destino = operacao.destino_uf
        regime = operacao.regime_tributario
    elif isinstance(operacao, dict):
        uf_origem = operacao.get("origem_uf", "SP")
        uf_destino = operacao.get("destino_uf", "RJ")
        regime = operacao.get("regime_tributario", "lucro_real")
    else:
        uf_origem = "SP"
        uf_destino = "RJ"
        regime = "lucro_real"

    # Get valid rates from Tool_Transicao for validation
    anos_simulados = [
        r.get("ano") if isinstance(r, dict) else getattr(r, "ano", None) for r in resultados_por_ano
    ]
    anos_simulados = [a for a in anos_simulados if a is not None]

    # Collect valid rates from both calculation results and Tool_Transicao
    valid_rates = _get_valid_rates_from_results(resultados_dicts)
    tool_rates = await _get_tool_rates_for_years(
        anos=anos_simulados,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        regime=regime,
    )
    valid_rates.update(tool_rates)

    # Also add common percentages that are valid (100%, 0%, phase-out %)
    valid_rates.update({0.0, 100.0, 90.0, 80.0, 70.0, 60.0})

    # Build prompt
    prompt = _build_prompt(
        trechos_rag=trechos_rag,
        resultados_por_ano=resultados_dicts,
        operacao=operacao,
    )

    # Generate justification with retry on rate mismatch
    justificativa: str | None = None
    attempt = 0
    max_attempts = 1 + MAX_JUSTIFICATION_RETRIES  # initial + 2 retries = 3 total

    while attempt < max_attempts:
        attempt += 1
        try:
            generated_text = await _call_llm(prompt)
        except Exception as exc:
            logger.error(
                "LLM call failed (attempt %d/%d): %s",
                attempt,
                max_attempts,
                str(exc),
                extra={"thread_id": thread_id},
            )
            if attempt < max_attempts:
                continue
            # All LLM call attempts exhausted
            break

        # Validate rates in generated text
        is_valid, mismatches = _validate_rates(generated_text, valid_rates)

        if is_valid:
            justificativa = generated_text
            logger.info(
                "Justification generated successfully (attempt %d/%d)",
                attempt,
                max_attempts,
                extra={"thread_id": thread_id},
            )
            break
        else:
            # Rate mismatch — discard and log integrity event
            logger.warning(
                "Rate mismatch in justification (attempt %d/%d): %s",
                attempt,
                max_attempts,
                mismatches,
                extra={
                    "event": "integridade",
                    "thread_id": thread_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "mismatches": mismatches,
                    "attempt": attempt,
                },
            )

            if attempt >= max_attempts:
                # All retries exhausted — escalate to human_review
                logger.error(
                    "All justification attempts failed rate validation. "
                    "Escalating to human_review.",
                    extra={
                        "event": "integridade",
                        "thread_id": thread_id,
                        "total_attempts": attempt,
                    },
                )

    # Determine outcome
    if justificativa is not None:
        # Generate analytical comment based on results
        comentario = _gerar_comentario_agente(resultados_dicts, operacao)
        return {
            "justificativa": justificativa,
            "comentario_agente": comentario,
            "alertas": alertas,
        }
    else:
        # Escalate to human_review
        alertas.append(
            "Justificativa descartada após múltiplas tentativas por inconsistência "
            "de alíquotas citadas. Escalado para revisão humana."
        )
        return {
            "justificativa": None,
            "comentario_agente": "",
            "revisao_manual": True,
            "alertas": alertas,
        }
