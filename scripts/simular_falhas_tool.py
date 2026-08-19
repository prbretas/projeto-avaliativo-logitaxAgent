"""Simular falhas na Tool_Transicao para teste de resiliência.

Simula 3 tipos de falha: timeout, resposta inválida, connection refused.
Mínimo 10 requests por tipo de falha.
Output: taxa de anomalia (failed/total) para stdout e
docs/devops/deteccao-anomalia.md.
Classificação de risco: low (<5%), medium (5-20%), high (>20%)
com ação de mitigação.

Requirements: 13.3, 13.4
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.client_transicao import consultar_tabela_transicao

REQUESTS_PER_TYPE = 10
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "devops"


@dataclass
class FaultResult:
    """Result of a single fault injection test."""

    fault_type: str
    request_num: int
    success: bool
    fallback_used: bool
    duration_ms: float
    error: str | None = None


@dataclass
class FaultSummary:
    """Summary for a fault type."""

    fault_type: str
    total_requests: int
    failed_requests: int
    fallback_used_count: int
    anomaly_rate_pct: float
    risk_level: str
    mitigation: str
    avg_duration_ms: float


def classify_risk(anomaly_rate: float) -> tuple[str, str]:
    """Classify risk level based on anomaly rate.

    Returns:
        Tuple of (risk_level, mitigation_action).
    """
    if anomaly_rate < 5.0:
        return "low", "Monitoramento padrão. Nenhuma ação necessária."
    elif anomaly_rate <= 20.0:
        return "medium", "Ativar alertas de observabilidade. Verificar logs de fallback."
    else:
        return "high", "Investigar causa raiz. Considerar circuit breaker ou fallback permanente."


async def simulate_timeout_faults() -> list[FaultResult]:
    """Simulate timeout faults (tool takes too long to respond)."""
    results = []

    for i in range(REQUESTS_PER_TYPE):
        start = time.perf_counter()
        try:
            # Patch httpx to simulate timeout
            with patch("src.tools.client_transicao.httpx.AsyncClient") as mock:
                import httpx

                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(
                    side_effect=httpx.TimeoutException("Connection timed out")
                )
                mock.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await consultar_tabela_transicao(
                    ano=2026, uf_origem="SP", uf_destino="RJ", regime="lucro_real"
                )
                duration = (time.perf_counter() - start) * 1000

                results.append(
                    FaultResult(
                        fault_type="timeout",
                        request_num=i + 1,
                        success=True,
                        fallback_used=result.fallback_usado,
                        duration_ms=round(duration, 2),
                    )
                )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            results.append(
                FaultResult(
                    fault_type="timeout",
                    request_num=i + 1,
                    success=False,
                    fallback_used=False,
                    duration_ms=round(duration, 2),
                    error=str(e),
                )
            )

    return results


async def simulate_invalid_response_faults() -> list[FaultResult]:
    """Simulate invalid response faults (tool returns garbage)."""
    results = []

    for i in range(REQUESTS_PER_TYPE):
        start = time.perf_counter()
        try:
            with patch("src.tools.client_transicao.httpx.AsyncClient") as mock:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json = lambda: {"invalid": "data", "no_required_fields": True}
                mock_response.raise_for_status = lambda: None

                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await consultar_tabela_transicao(
                    ano=2027, uf_origem="MG", uf_destino="BA", regime="lucro_presumido"
                )
                duration = (time.perf_counter() - start) * 1000

                results.append(
                    FaultResult(
                        fault_type="invalid_response",
                        request_num=i + 1,
                        success=True,
                        fallback_used=result.fallback_usado,
                        duration_ms=round(duration, 2),
                    )
                )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            results.append(
                FaultResult(
                    fault_type="invalid_response",
                    request_num=i + 1,
                    success=False,
                    fallback_used=False,
                    duration_ms=round(duration, 2),
                    error=str(e),
                )
            )

    return results


async def simulate_connection_refused_faults() -> list[FaultResult]:
    """Simulate connection refused faults (tool is down)."""
    results = []

    for i in range(REQUESTS_PER_TYPE):
        start = time.perf_counter()
        try:
            with patch("src.tools.client_transicao.httpx.AsyncClient") as mock:
                import httpx

                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
                mock.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await consultar_tabela_transicao(
                    ano=2033, uf_origem="RJ", uf_destino="SP", regime="simples_nacional"
                )
                duration = (time.perf_counter() - start) * 1000

                results.append(
                    FaultResult(
                        fault_type="connection_refused",
                        request_num=i + 1,
                        success=True,
                        fallback_used=result.fallback_usado,
                        duration_ms=round(duration, 2),
                    )
                )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            results.append(
                FaultResult(
                    fault_type="connection_refused",
                    request_num=i + 1,
                    success=False,
                    fallback_used=False,
                    duration_ms=round(duration, 2),
                    error=str(e),
                )
            )

    return results


def summarize_results(results: list[FaultResult], fault_type: str) -> FaultSummary:
    """Summarize results for a fault type."""
    total = len(results)
    failed = sum(1 for r in results if not r.success)
    fallback_count = sum(1 for r in results if r.fallback_used)
    anomaly_rate = (failed / total * 100) if total > 0 else 0.0
    avg_duration = sum(r.duration_ms for r in results) / total if total > 0 else 0.0
    risk_level, mitigation = classify_risk(anomaly_rate)

    return FaultSummary(
        fault_type=fault_type,
        total_requests=total,
        failed_requests=failed,
        fallback_used_count=fallback_count,
        anomaly_rate_pct=round(anomaly_rate, 2),
        risk_level=risk_level,
        mitigation=mitigation,
        avg_duration_ms=round(avg_duration, 2),
    )


def generate_report(summaries: list[FaultSummary]) -> str:
    """Generate markdown report for docs/devops/deteccao-anomalia.md."""
    report = "# Detecção de Anomalias — Tool_Transicao\n\n"
    report += "## Resumo da Simulação de Falhas\n\n"
    report += (
        "| Tipo de Falha | Requests | Falhas | Fallback | Taxa Anomalia | Risco | Mitigação |\n"
    )
    report += "|---|---|---|---|---|---|---|\n"

    for s in summaries:
        report += (
            f"| {s.fault_type} | {s.total_requests} | {s.failed_requests} | "
            f"{s.fallback_used_count} | {s.anomaly_rate_pct}% | "
            f"**{s.risk_level}** | {s.mitigation} |\n"
        )

    report += "\n## Detalhes\n\n"
    for s in summaries:
        report += f"### {s.fault_type}\n\n"
        report += f"- Total requests: {s.total_requests}\n"
        report += f"- Falhas: {s.failed_requests}\n"
        report += f"- Fallback acionado: {s.fallback_used_count}\n"
        report += f"- Taxa de anomalia: {s.anomaly_rate_pct}%\n"
        report += f"- Tempo médio: {s.avg_duration_ms}ms\n"
        report += f"- Nível de risco: {s.risk_level}\n"
        report += f"- Ação de mitigação: {s.mitigation}\n\n"

    report += "## Classificação de Risco\n\n"
    report += "- **low** (<5%): Monitoramento padrão\n"
    report += "- **medium** (5-20%): Ativar alertas\n"
    report += "- **high** (>20%): Investigar causa raiz\n"

    return report


async def main():
    """Run all fault simulations and output results."""
    print("=== Simulação de Falhas — Tool_Transicao ===\n")

    # Run simulations
    print("Simulando timeout...")
    timeout_results = await simulate_timeout_faults()
    timeout_summary = summarize_results(timeout_results, "timeout")

    print("Simulando resposta inválida...")
    invalid_results = await simulate_invalid_response_faults()
    invalid_summary = summarize_results(invalid_results, "invalid_response")

    print("Simulando connection refused...")
    refused_results = await simulate_connection_refused_faults()
    refused_summary = summarize_results(refused_results, "connection_refused")

    summaries = [timeout_summary, invalid_summary, refused_summary]

    # Output to stdout
    print("\n=== Resultados ===\n")
    for s in summaries:
        print(
            f"  {s.fault_type}: {s.failed_requests}/{s.total_requests} falhas "
            f"({s.anomaly_rate_pct}%) — risco: {s.risk_level}"
        )

    # Generate markdown report
    report = generate_report(summaries)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "deteccao-anomalia.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"\nRelatório salvo em: {output_path}")

    # JSON output
    json_output = json.dumps([asdict(s) for s in summaries], ensure_ascii=False, indent=2)
    print(f"\nJSON:\n{json_output}")


if __name__ == "__main__":
    asyncio.run(main())
