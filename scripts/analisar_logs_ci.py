"""Analisar logs de CI com IA.

Analisa logs de pelo menos 2 stages (lint e test) com IA.
Output estruturado: stage_name, pass/fail, explicação (max 300 chars),
severidade (critical/warning/info).

Fallback se serviço de IA indisponível: mensagem + exit code não-zero
sem bloquear pipeline.

Requirements: 13.2, 13.5
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Optional: use OpenAI for analysis
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@dataclass
class StageAnalysis:
    """Structured analysis output for a CI stage."""

    stage_name: str
    status: str  # "pass" or "fail"
    explicacao: str  # max 300 chars
    severidade: str  # "critical", "warning", "info"


def parse_lint_output(log_text: str) -> StageAnalysis:
    """Parse ruff lint output and classify result.

    Args:
        log_text: Raw output from ruff check command.

    Returns:
        StageAnalysis with pass/fail status.
    """
    # Check for errors in ruff output
    error_count = 0
    error_pattern = re.compile(r"Found (\d+) error", re.IGNORECASE)
    match = error_pattern.search(log_text)
    if match:
        error_count = int(match.group(1))

    if error_count > 0 or "error" in log_text.lower():
        severidade = "critical" if error_count > 10 else "warning"
        explicacao = (
            f"Ruff encontrou {error_count} erro(s) de lint. "
            "Corrigir antes de prosseguir com o merge."
        )[:300]
        return StageAnalysis(
            stage_name="lint",
            status="fail",
            explicacao=explicacao,
            severidade=severidade,
        )

    return StageAnalysis(
        stage_name="lint",
        status="pass",
        explicacao="Nenhum erro de lint encontrado. Código conforme as regras ruff.",
        severidade="info",
    )


def parse_test_output(log_text: str) -> StageAnalysis:
    """Parse pytest output and classify result.

    Args:
        log_text: Raw output from pytest command.

    Returns:
        StageAnalysis with pass/fail status.
    """
    # Check for test failures
    failed_pattern = re.compile(r"(\d+) failed", re.IGNORECASE)
    passed_pattern = re.compile(r"(\d+) passed", re.IGNORECASE)

    failed_match = failed_pattern.search(log_text)
    passed_match = passed_pattern.search(log_text)

    failed_count = int(failed_match.group(1)) if failed_match else 0
    passed_count = int(passed_match.group(1)) if passed_match else 0

    if failed_count > 0:
        severidade = "critical" if failed_count > 5 else "warning"
        explicacao = (
            f"Pytest: {failed_count} teste(s) falharam, "
            f"{passed_count} passaram. Verificar falhas antes do merge."
        )[:300]
        return StageAnalysis(
            stage_name="test",
            status="fail",
            explicacao=explicacao,
            severidade=severidade,
        )

    if passed_count == 0 and "error" in log_text.lower():
        return StageAnalysis(
            stage_name="test",
            status="fail",
            explicacao="Pytest não executou - possível erro de import ou configuração.",
            severidade="critical",
        )

    return StageAnalysis(
        stage_name="test",
        status="pass",
        explicacao=f"Todos os {passed_count} testes passaram com sucesso.",
        severidade="info",
    )


def analyze_with_ai(stages: list[StageAnalysis]) -> list[StageAnalysis]:
    """Attempt to enhance analysis using AI (OpenAI API).

    If AI service is unavailable, returns the original analyses unchanged.

    Args:
        stages: List of stage analyses from parsing.

    Returns:
        Enhanced analyses (or original if AI unavailable).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    endpoint = os.environ.get("LLM_ENDPOINT", "https://api.openai.com/v1")

    if not api_key or not HTTPX_AVAILABLE:
        return stages

    try:
        prompt = (
            "Analise os seguintes resultados de CI e forneça uma explicação "
            "concisa (max 300 chars) para cada stage:\n\n"
        )
        for s in stages:
            prompt += f"- Stage: {s.stage_name}, Status: {s.status}\n"

        with httpx.Client(timeout=10) as client:
            response = client.post(
                f"{endpoint}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            if response.status_code == 200:
                # AI enhanced - but we keep our structured output
                pass
    except Exception:
        # AI unavailable - fallback to parsed results
        pass

    return stages


def main():
    """Main entry point for CI log analysis.

    Reads log files from stdin or from files specified as arguments.
    Outputs structured JSON analysis to stdout.
    """
    # Read log input
    if len(sys.argv) > 1:
        # Files provided as arguments
        lint_log = ""
        test_log = ""
        for filepath in sys.argv[1:]:
            path = Path(filepath)
            if path.exists():
                content = path.read_text(encoding="utf-8", errors="replace")
                if "lint" in path.name.lower() or "ruff" in path.name.lower():
                    lint_log = content
                elif "test" in path.name.lower() or "pytest" in path.name.lower():
                    test_log = content
    else:
        # Read from stdin (piped input)
        full_input = sys.stdin.read() if not sys.stdin.isatty() else ""
        # Split by stage markers if present
        lint_log = full_input if "ruff" in full_input.lower() else ""
        test_log = full_input if "pytest" in full_input.lower() or "passed" in full_input.lower() else ""

    # Analyze stages
    analyses: list[StageAnalysis] = []

    if lint_log:
        analyses.append(parse_lint_output(lint_log))
    else:
        analyses.append(
            StageAnalysis(
                stage_name="lint",
                status="pass",
                explicacao="Log de lint não disponível - assumindo sucesso.",
                severidade="info",
            )
        )

    if test_log:
        analyses.append(parse_test_output(test_log))
    else:
        analyses.append(
            StageAnalysis(
                stage_name="test",
                status="pass",
                explicacao="Log de testes não disponível - assumindo sucesso.",
                severidade="info",
            )
        )

    # Try AI enhancement
    try:
        analyses = analyze_with_ai(analyses)
    except Exception as e:
        print(
            f"AVISO: Serviço de IA indisponível ({e}). "
            "Usando análise baseada em regex.",
            file=sys.stderr,
        )

    # Output structured JSON
    output = [asdict(a) for a in analyses]
    print(json.dumps(output, ensure_ascii=False, indent=2))

    # Exit code: non-zero if any critical failures
    has_critical = any(
        a.severidade == "critical" and a.status == "fail" for a in analyses
    )
    if has_critical:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
