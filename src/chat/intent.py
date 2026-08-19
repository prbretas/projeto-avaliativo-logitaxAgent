"""Intent extraction and parameter parsing for conversational interface.

Extracts user intent from natural language messages and maps them to
actions the agent can perform:
- "simular": user wants a tax simulation (extract params)
- "comparar": user wants to compare regimes or scenarios
- "legislacao": user asks about legislation (route to RAG)
- "explicar": user asks for explanation of previous result
- "saudacao": greeting/chitchat

Uses LLM (OpenAI-compatible) when available, with regex fallback
when no API key is configured.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "https://api.openai.com/v1")
LLM_TIMEOUT = 15.0

# Valid UFs and regimes for extraction
UFS_VALIDAS = {
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
}

REGIMES = {
    "lucro_real": ["lucro real", "real"],
    "lucro_presumido": ["lucro presumido", "presumido"],
    "simples_nacional": ["simples nacional", "simples", "mei"],
}

MODAIS = {
    "rodoviario": ["rodoviário", "rodoviario", "caminhão", "caminhao", "truck"],
    "aereo": ["aéreo", "aereo", "avião", "aviao", "air"],
    "ferroviario": ["ferroviário", "ferroviario", "trem", "ferrovia"],
    "aquaviario": ["aquaviário", "aquaviario", "navio", "barco", "maritimo"],
}


class ParsedIntent:
    """Result of intent extraction from a user message."""

    def __init__(
        self,
        intent: str,
        params: dict[str, Any] | None = None,
        confidence: float = 1.0,
        missing_params: list[str] | None = None,
    ):
        self.intent = intent
        self.params = params or {}
        self.confidence = confidence
        self.missing_params = missing_params or []

    def is_complete_for_simulation(self) -> bool:
        """Check if all required params for simulation are present."""
        required = {"valor_frete", "origem_uf", "destino_uf", "regime_tributario"}
        return required.issubset(set(self.params.keys()))


def extract_intent(message: str, context: dict[str, Any] | None = None) -> ParsedIntent:
    """Extract intent and parameters from a user message.

    First tries LLM-based extraction, falls back to regex if no API key.

    Args:
        message: User's natural language input.
        context: Previous conversation context (for follow-up questions).

    Returns:
        ParsedIntent with intent type and extracted parameters.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            return _extract_with_llm(message, context, api_key)
        except Exception as e:
            logger.warning("LLM intent extraction failed: %s. Using fallback.", e)

    return _extract_with_regex(message, context)


def _extract_with_llm(message: str, context: dict[str, Any] | None, api_key: str) -> ParsedIntent:
    """Extract intent using LLM with structured output."""
    context_str = ""
    if context:
        context_str = f"\nContexto anterior: {json.dumps(context, ensure_ascii=False, default=str)}"

    system_prompt = """Você é um parser de intenção para um simulador tributário de frete.
Extraia a intenção e parâmetros da mensagem do usuário.

Retorne APENAS um JSON válido com esta estrutura:
{
  "intent": "simular" | "comparar" | "legislacao" | "explicar" | "saudacao",
  "params": {
    "valor_frete": float ou null,
    "origem_uf": "XX" ou null,
    "destino_uf": "XX" ou null,
    "regime_tributario": "lucro_real" | "lucro_presumido" | "simples_nacional" | null,
    "modal": "rodoviario" | "aereo" | "ferroviario" | "aquaviario" | null,
    "ano": int ou null
  },
  "missing_params": ["lista de params obrigatorios ausentes"]
}

Regras:
- Se o usuário menciona valor em reais, extraia como valor_frete
- UFs são códigos de 2 letras (SP, RJ, MG, BA, etc.)
- Se menciona "simples", regime é "simples_nacional"
- Se não menciona modal, assuma "rodoviario"
- Se não menciona ano, deixe null
- "legislacao" = perguntas sobre leis, artigos, alíquotas sem pedir simulação
- "explicar" = pedir explicação de resultado anterior
- "comparar" = pedir comparação entre regimes ou cenários"""

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{message}{context_str}"},
        ],
        "temperature": 0.1,
        "max_tokens": 300,
    }

    with httpx.Client(timeout=LLM_TIMEOUT) as client:
        response = client.post(
            f"{LLM_ENDPOINT}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    text = data["choices"][0]["message"]["content"].strip()

    # Parse JSON from response (handle markdown code blocks)
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    parsed = json.loads(text)

    # Clean params (remove nulls)
    params = {k: v for k, v in parsed.get("params", {}).items() if v is not None}

    return ParsedIntent(
        intent=parsed.get("intent", "simular"),
        params=params,
        confidence=0.9,
        missing_params=parsed.get("missing_params", []),
    )


def _extract_with_regex(message: str, context: dict[str, Any] | None) -> ParsedIntent:
    """Fallback intent extraction using regex patterns."""
    msg_lower = message.lower().strip()

    # Check for greetings
    greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hello", "hi"]
    if any(msg_lower.startswith(g) for g in greetings) and len(msg_lower) < 30:
        return ParsedIntent(intent="saudacao")

    # Check for legislation questions
    leg_keywords = [
        "artigo",
        "lei",
        "lc 214",
        "legislação",
        "legislacao",
        "qual alíquota",
        "qual aliquota",
        "quando começa",
        "quando comeca",
    ]
    if any(kw in msg_lower for kw in leg_keywords):
        return ParsedIntent(intent="legislacao", params={"pergunta": message})

    # Check for explanation requests
    explain_keywords = ["por que", "porque", "explica", "como assim", "o que significa"]
    if any(kw in msg_lower for kw in explain_keywords):
        return ParsedIntent(intent="explicar", params={"pergunta": message})

    # Check for comparison requests
    compare_keywords = ["compara", "comparar", "diferença", "diferenca", "versus", "vs"]
    if any(kw in msg_lower for kw in compare_keywords):
        return ParsedIntent(intent="comparar", params={"pergunta": message})

    # Default: try to extract simulation parameters
    params: dict[str, Any] = {}

    # Extract valor_frete (numbers with R$, mil, etc.)
    valor_match = re.search(r"r\$\s*([\d.,]+)|(\d[\d.,]*)\s*(mil|reais|r\$)", msg_lower)
    if valor_match:
        val_str = valor_match.group(1) or valor_match.group(2)
        val_str = val_str.replace(".", "").replace(",", ".")
        try:
            valor = float(val_str)
            if valor_match.group(3) == "mil":
                valor *= 1000
            params["valor_frete"] = valor
        except ValueError:
            pass

    # Also try plain large numbers
    if "valor_frete" not in params:
        num_match = re.search(r"(\d{4,})", message)
        if num_match:
            params["valor_frete"] = float(num_match.group(1))

    # Extract UFs
    uf_matches = re.findall(r"\b([A-Z]{2})\b", message.upper())
    valid_ufs = [u for u in uf_matches if u in UFS_VALIDAS]
    if len(valid_ufs) >= 2:
        params["origem_uf"] = valid_ufs[0]
        params["destino_uf"] = valid_ufs[1]
    elif len(valid_ufs) == 1:
        # Check for "de X para Y" pattern
        params["origem_uf"] = valid_ufs[0]

    # Extract regime
    for regime_key, keywords in REGIMES.items():
        if any(kw in msg_lower for kw in keywords):
            params["regime_tributario"] = regime_key
            break

    # Extract modal
    for modal_key, keywords in MODAIS.items():
        if any(kw in msg_lower for kw in keywords):
            params["modal"] = modal_key
            break

    # Extract year
    year_match = re.search(r"\b(202[6-9]|203[0-3])\b", message)
    if year_match:
        params["ano"] = int(year_match.group(1))

    # Fill from context if available
    if context:
        for key in ["origem_uf", "destino_uf", "regime_tributario", "modal", "valor_frete"]:
            if key not in params and key in context:
                params[key] = context[key]

    # Determine missing required params
    required = {"valor_frete", "origem_uf", "destino_uf", "regime_tributario"}
    missing = [p for p in required if p not in params]

    # Set defaults
    params.setdefault("modal", "rodoviario")

    return ParsedIntent(
        intent="simular",
        params=params,
        confidence=0.6 if missing else 0.8,
        missing_params=missing,
    )
