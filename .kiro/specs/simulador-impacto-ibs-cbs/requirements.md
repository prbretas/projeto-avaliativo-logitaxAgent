# Requirements Document

## Introduction

O **logitaxAgent** é um sistema híbrido agêntico (LangGraph) que simula o impacto financeiro da Reforma Tributária brasileira (LC 214/2025) sobre operações de frete. O sistema compara a carga tributária do regime atual (PIS + COFINS + ICMS) com o regime IBS/CBS ao longo dos anos de transição (2026–2033), permitindo que analistas fiscais e logísticos avaliem reajustes contratuais antes da transição avançar.

Classificação: **sistema híbrido** — o fluxo determinístico calcula tributos; o LLM atua apenas na geração de justificativa em linguagem natural citando legislação e no roteamento de intenção.

Limitação conhecida: a alíquota de ICMS interestadual utiliza valor fixo simplificado (~12%) em vez da tabela completa CONFAZ por par de UFs.

## Glossary

- **logitaxAgent**: Sistema híbrido agêntico que simula o impacto financeiro IBS/CBS no frete
- **Simulador**: Módulo principal do logitaxAgent responsável pelo cálculo comparativo de carga tributária
- **CT_e**: Conhecimento de Transporte eletrônico — documento fiscal do frete rodoviário de cargas
- **cClassTrib**: Código de Classificação Tributária exigido no CT-e (NT 2025.001)
- **IBS**: Imposto sobre Bens e Serviços (estadual/municipal) instituído pela LC 214/2025
- **CBS**: Contribuição sobre Bens e Serviços (federal) instituída pela LC 214/2025
- **Regime_Atual**: Conjunto de tributos vigentes sobre frete: PIS (1,65%) + COFINS (7,6%) + ICMS (~12%)
- **Regime_Novo**: Conjunto IBS + CBS com alíquotas progressivas conforme ano de transição (2026–2033)
- **Tabela_Transicao**: Fonte determinística de alíquotas por ano, versionada em JSON local com fallback
- **Tool_Transicao**: Endpoint FastAPI `GET /tools/tabela-transicao` que consulta a Tabela_Transicao
- **Fan_Out**: Execução paralela de nodes LangGraph para múltiplos anos-marco simultaneamente
- **Fan_In**: Agregação dos resultados parciais de cada ano em um resultado consolidado
- **RAG**: Recuperação Aumentada por Geração — busca vetorial em ChromaDB sobre trechos da LC 214/2025
- **Human_Review**: Ponto de interrupção (interrupt) onde o operador humano aprova ou rejeita a exportação
- **Thread_Id**: Identificador único de sessão usado para correlacionar logs, auditoria e histórico
- **Embarcador**: Contratante do frete, usuário principal do sistema de simulação
- **Simples_Nacional**: Regime tributário diferenciado para microempresas e empresas de pequeno porte
- **Delta_Percentual**: Diferença percentual entre a carga tributária do Regime_Atual e do Regime_Novo
- **Webhook_N8n**: Endpoint HTTP consumido pelo n8n para disparar fluxo de alerta low-code
- **Sanitizador**: Node do grafo que neutraliza tentativas de prompt injection em campos de texto livre

## Requirements

### Requirement 1: Entrada e validação da operação de frete

**User Story:** As an analista fiscal de um embarcador, I want to submit a freight operation with all required parameters, so that the Simulador can calculate the tax comparison accurately.

#### Acceptance Criteria

1. WHEN the user submits a freight operation containing modal (one of: rodoviario, aereo, ferroviario, aquaviario), origin UF, destination UF, tax regime (one of: lucro_real, lucro_presumido, simples_nacional), freight value, and reference date, THE Simulador SHALL accept the operation and proceed to tax calculation.
2. IF the freight value is less than or equal to zero or greater than 999,999,999.99, THEN THE Simulador SHALL reject the operation with a structured error message identifying the invalid field.
3. IF the origin UF or destination UF is not a valid Brazilian state code (one of the 27 two-letter codes: AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PB, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO), THEN THE Simulador SHALL reject the operation with a structured error message identifying the invalid UF.
4. IF the reference date year is outside the range 2026–2033, THEN THE Simulador SHALL reject the operation with a structured error message stating the supported range.
5. IF any required field (modal, origin UF, destination UF, tax regime, freight value, reference date) is missing, THEN THE Simulador SHALL reject the operation with a structured error message listing all missing fields.
6. IF the modal is not one of the accepted values (rodoviario, aereo, ferroviario, aquaviario) or the tax regime is not one of the accepted values (lucro_real, lucro_presumido, simples_nacional), THEN THE Simulador SHALL reject the operation with a structured error message identifying the invalid field and listing the accepted values.
7. THE Simulador SHALL validate all input fields using Pydantic schema enforcement before any downstream node executes.
8. WHEN the Simulador rejects an operation due to one or more validation errors, THE Simulador SHALL return all detected validation errors in a single structured response within 1 second of submission, without executing any tax calculation node.

### Requirement 2: Cálculo comparativo de carga tributária

**User Story:** As an analista logístico, I want to see the tax burden under both the current regime and the IBS/CBS regime for a given year, so that I can assess the financial impact on freight contracts.

#### Acceptance Criteria

1. WHEN the Simulador receives a valid freight operation with a specific reference year, THE Simulador SHALL calculate the tax value under the Regime_Atual (PIS 1.65% + COFINS 7.6% + ICMS 12.0% fixed) and the Regime_Novo (IBS + CBS per Tabela_Transicao for that year), rounding monetary results to 2 decimal places and percentages to 2 decimal places.
2. WHEN the reference year is 2026, THE Simulador SHALL apply the test-phase combined rate of 1.0% (CBS 0.9% + IBS 0.1%) as defined in LC 214/2025 arts. 343, 346, and 348.
3. WHEN the reference year is 2027 or 2028, THE Simulador SHALL apply the CBS rate from the Tabela_Transicao (replacing PIS and COFINS) combined with the IBS residual rate from the Tabela_Transicao for that year, while maintaining ICMS at 100% of the base rate.
4. WHEN the reference year is between 2029 and 2032, THE Simulador SHALL apply the ICMS phase-out percentage for that year (90%/80%/70%/60% of the 12.0% base ICMS) combined with the CBS rate and the proportional IBS rate (10%/20%/30%/40% of full IBS) as defined in the Tabela_Transicao.
5. WHEN the reference year is 2033, THE Simulador SHALL apply ICMS at 0% and use the full IBS rate plus the CBS rate from the Tabela_Transicao, representing the complete transition to Regime_Novo.
6. WHEN the Simulador completes calculation for a year, THE Simulador SHALL return: tax value under Regime_Atual, tax value under Regime_Novo, Delta_Percentual calculated as ((valor_tributo_novo − valor_tributo_atual) / valor_tributo_atual) × 100, data source identifier, and a flag indicating whether fallback data was used.
7. THE Simulador SHALL obtain all tax rates exclusively from the Tool_Transicao or the local Tabela_Transicao fallback, and SHALL NOT use rates generated by the LLM.

### Requirement 3: Paralelização por anos-marco (fan-out/fan-in)

**User Story:** As an analista fiscal, I want to see the tax impact across multiple transition milestones in a single request, so that I can plan for the entire transition period without submitting separate queries.

#### Acceptance Criteria

1. WHEN the user does not specify a reference year, THE Simulador SHALL execute tax calculations in parallel (Fan_Out) for the years 2026, 2027, 2030, and 2033.
2. WHEN all parallel calculations complete successfully, THE Simulador SHALL aggregate (Fan_In) all partial results into a single consolidated response containing one result set per year simulated, ordered chronologically by year.
3. WHEN the user specifies a single reference year, THE Simulador SHALL calculate only for that year without invoking Fan_Out.
4. THE Simulador SHALL implement Fan_Out using LangGraph parallel node execution, not sequential iteration.
5. IF one or more parallel year calculations fail during Fan_Out (due to tool timeout, validation error, or unavailability), THEN THE Simulador SHALL return a partial consolidated response containing the successful year results and, for each failed year, an entry indicating the failure reason and the year that could not be calculated.
6. IF all parallel year calculations fail during Fan_Out, THEN THE Simulador SHALL return a structured error message indicating that no year could be calculated and listing the failure reason for each year attempted.

### Requirement 4: Roteamento condicional por regime tributário

**User Story:** As an transportador optante do Simples Nacional, I want the simulation to apply the correct tax rules for my regime, so that the results reflect my actual obligations.

#### Acceptance Criteria

1. WHEN the freight operation specifies Simples_Nacional as the tax regime, THE Simulador SHALL route execution to the node `simular_regime_hibrido_simples` which calculates Regime_Novo without non-cumulative IBS/CBS credit deductions (credit = 0), reflecting the restricted credit rules of Simples Nacional.
2. WHEN the freight operation specifies lucro_real or lucro_presumido as the tax regime, THE Simulador SHALL route execution to the `simular_regime_regular` node which calculates Regime_Novo applying full non-cumulative IBS/CBS credit deductions as defined in the Tabela_Transicao.
3. THE Simulador SHALL implement regime routing as a conditional edge in the LangGraph StateGraph, using the `regime_tributario` field of OperacaoFrete as the sole branching criterion.
4. IF the freight operation specifies a tax regime value not in the set {lucro_real, lucro_presumido, simples_nacional}, THEN THE Simulador SHALL reject the operation with a structured error message identifying the invalid regime value and listing the accepted values.
5. WHEN two freight operations are identical except for tax regime (one Simples_Nacional, one lucro_real), THE Simulador SHALL return different Regime_Novo tax values for the same reference year, confirming that the routing produces differentiated calculation results.

### Requirement 5: Tool externa de consulta de alíquotas (MCP/API)

**User Story:** As a developer, I want the system to consult tax rates through a validated API tool, so that rates are deterministic, versioned, and auditable.

#### Acceptance Criteria

1. THE Tool_Transicao SHALL expose the endpoint `GET /tools/tabela-transicao` accepting parameters: ano, uf_origem, uf_destino, and regime, with Pydantic-validated request and response schemas, and SHALL include in the response body a `versao` field identifying the data version used.
2. IF the Tool_Transicao receives a year outside 2026–2033, THEN THE Tool_Transicao SHALL return HTTP 422 with a structured error body identifying the invalid parameter.
3. IF the Tool_Transicao receives an invalid UF code, THEN THE Tool_Transicao SHALL return HTTP 422 with a structured error body identifying the invalid parameter.
4. IF the Tool_Transicao receives a regime value other than lucro_real, lucro_presumido, or simples_nacional, THEN THE Tool_Transicao SHALL return HTTP 422 with a structured error body identifying the invalid parameter.
5. WHEN a call to the Tool_Transicao exceeds the configured timeout (5 seconds), THE Simulador SHALL retry up to 2 times with exponential backoff starting at a base delay of 1 second (delays of 1 s, then 2 s).
6. IF all retries to the Tool_Transicao fail, THEN THE Simulador SHALL fall back to the local Tabela_Transicao JSON file and set the `fallback_usado` flag to true in the result.
7. WHEN fallback data is used, THE Simulador SHALL include a warning in the response containing the fallback file version identifier and stating that rates may differ from the latest available source.

### Requirement 6: Condição de parada e limites de autonomia

**User Story:** As a responsável técnico, I want the system to have explicit stopping conditions, so that it cannot loop indefinitely on ambiguous cases.

#### Acceptance Criteria

1. THE Simulador SHALL maintain a counter `tentativas_reclassificacao` in the AgentState, initialized at 0 for each new freight operation.
2. WHEN the Simulador executes a reclassification action (re-routing through `route_regime` or re-invoking a simulation node due to ambiguous or inconsistent intermediate results), THE Simulador SHALL increment `tentativas_reclassificacao` by 1.
3. WHEN `tentativas_reclassificacao` reaches 3, THE Simulador SHALL force transition to Human_Review with the flag `revisao_manual` set to true and SHALL include in the state the partial results collected up to that point and the reason for escalation.
4. THE Simulador SHALL NOT permit more than 3 reclassification attempts for a single freight operation, regardless of the source triggering the reclassification.
5. IF a freight operation arrives at Human_Review due to the reclassification limit being reached, THEN THE Simulador SHALL NOT re-enter the reclassification loop for that same operation after human decision, terminating the flow upon human rejection or proceeding to export upon human approval.

### Requirement 7: Justificativa com RAG e citação legislativa

**User Story:** As an analista fiscal, I want the justification to cite real legislation, so that I can trust the simulation without manually cross-referencing the law.

#### Acceptance Criteria

1. THE logitaxAgent SHALL maintain a ChromaDB vector index containing excerpts from LC 214/2025, EC 132/2023, and CT-e Technical Notes related to freight transport, with each chunk annotated with metadata fields: source law identifier, article number, and applicable year range.
2. WHEN the node `generate_justification` executes, THE logitaxAgent SHALL retrieve up to 5 chunks from the RAG index filtered by the simulation scenario (year, regime) and include at least one source citation per referenced legal provision, formatted as article number and law identifier (e.g., "art. 343, LC 214/2025").
3. IF the RAG retrieval returns zero chunks matching the simulation scenario filters, THEN THE logitaxAgent SHALL generate the justification using the rates from Tool_Transicao without legislative citations and include a warning indicating that no legislative source was found for the given scenario.
4. THE logitaxAgent SHALL ensure that cited tax rates in the justification text match exactly the rates returned by the Tool_Transicao for the same scenario.
5. IF a cited tax rate in the generated justification does not match the rate returned by Tool_Transicao for the same scenario, THEN THE logitaxAgent SHALL discard the justification, log the mismatch as an integrity event in the audit trail, and retry justification generation up to 2 additional times before escalating to Human_Review.
6. WHEN the regulatory base is updated (new Technical Note or legislative amendment), THE logitaxAgent SHALL provide a reingestion process via `scripts/run_ingestao.py` that executes without manual intervention beyond invocation and logs the number of chunks indexed and any parsing errors encountered.

### Requirement 8: Memória de sessão por thread

**User Story:** As an analista fiscal, I want to ask follow-up questions about previous simulations in the same session, so that I do not need to re-submit the entire operation.

#### Acceptance Criteria

1. THE logitaxAgent SHALL persist simulation state per Thread_Id using a SQLite checkpointer, where simulation state includes: validated input parameters, tax values under Regime_Atual and Regime_Novo, Delta_Percentual, data source identifier, fallback flag, and generated justification text.
2. WHEN a user sends a follow-up query within the same Thread_Id, THE logitaxAgent SHALL retrieve the most recent simulation results from the checkpointer and use them as context for the response without requiring re-submission of input data.
3. IF a user sends a query with a Thread_Id that has no prior simulation state stored, THEN THE logitaxAgent SHALL respond with an error message indicating that no previous simulation exists for that session and request full input parameters.
4. THE logitaxAgent SHALL retain session state in the SQLite checkpointer for a maximum of 72 hours after the last interaction on that Thread_Id, after which the state may be purged.

### Requirement 9: Segurança contra prompt injection

**User Story:** As a responsável técnico, I want the system to resist prompt injection attacks in free-text fields, so that malicious input cannot bypass controls or leak sensitive data.

#### Acceptance Criteria

1. WHEN a freight operation contains free-text content (campo observacoes) of up to 500 characters, THE Sanitizador SHALL wrap that content in a fenced delimiter block with an explicit "UNTRUSTED_USER_DATA" label and strip any content exceeding 500 characters before any prompt composition.
2. IF the observacoes field contains keywords or patterns associated with prompt injection (including but not limited to: imperative verbs directed at the system such as "ignore", "override", "skip", "forget", combined with references to rules, instructions, or approvals), THEN THE Simulador SHALL treat the entire field as inert data, continue requiring Human_Review approval, and log a security event in the audit trail containing Thread_Id, timestamp, the triggering pattern detected, and the raw input hash.
3. THE Simulador SHALL NOT expose API keys, environment secrets, or internal prompt templates in any response, regardless of input content.
4. THE logitaxAgent SHALL store credentials exclusively in environment variables, with only a `.env.example` (containing no real values) committed to the repository.
5. IF the Sanitizador node fails to process the observacoes field (timeout exceeding 3 seconds or unhandled exception), THEN THE Simulador SHALL block the operation from proceeding to prompt composition, return a structured error indicating sanitization failure, and log the failure as a security event in the audit trail.

### Requirement 10: Human-in-the-loop antes da exportação

**User Story:** As a gestor de frete, I want to approve simulation results before they are exported or trigger downstream actions, so that no incorrect data influences contract decisions.

#### Acceptance Criteria

1. WHEN the Simulador completes the justification phase, THE Simulador SHALL pause execution at the Human_Review interrupt point, present the simulation summary (tax values for each regime, Delta_Percentual, fallback flag, and justification text), and await explicit human approval or rejection.
2. IF the human rejects the result, THEN THE Simulador SHALL log the rejection with timestamp, Thread_Id, and the human-provided rejection reason in the audit trail, and terminate the flow without exporting.
3. WHEN the human approves the result, THE Simulador SHALL proceed to export_result which persists the JSON output and dispatches the webhook to Webhook_N8n within 10 seconds of approval.
4. THE Simulador SHALL NOT export results or trigger the Webhook_N8n without prior human approval, regardless of the source of the request (API, low-code, or internal).
5. IF the Human_Review interrupt remains pending without a human response for more than 24 hours, THEN THE Simulador SHALL mark the session as expired, log the timeout with Thread_Id in the audit trail, and terminate the flow without exporting.
6. WHILE the Human_Review interrupt is pending, THE Simulador SHALL allow the human to retrieve the simulation summary for that Thread_Id at any time without altering the pending state.

### Requirement 11: Observabilidade correlacionada

**User Story:** As a operador do sistema, I want to reconstruct any past execution step-by-step, so that I can investigate anomalies without having been present during execution.

#### Acceptance Criteria

1. THE logitaxAgent SHALL emit structured JSON logs for each graph node execution, containing: Thread_Id, node name, ISO 8601 timestamp, duration in integer milliseconds (≥ 0), and status (success or error type).
2. THE logitaxAgent SHALL maintain an audit table in SQLite recording human decisions (approve/reject), security events (prompt injection attempts, unauthorized access attempts), and fallback activations, each record containing Thread_Id, event type, ISO 8601 timestamp, and relevant payload.
3. WHEN a node execution fails (tool timeout, validation error), THE logitaxAgent SHALL log the error type and the recovery action taken (retry, fallback, or escalation to Human_Review).
4. WHEN a user queries the endpoint `GET /observabilidade/{thread_id}` with a valid Thread_Id that has associated records, THE logitaxAgent SHALL return the complete timeline of node executions and audit events for that thread, ordered chronologically by timestamp, within 2 seconds.
5. IF a user queries `GET /observabilidade/{thread_id}` with a Thread_Id that does not exist in the system, THEN THE logitaxAgent SHALL return a structured error response indicating that no records were found for the given Thread_Id.

### Requirement 12: QA assistido por IA

**User Story:** As a desenvolvedor solo, I want AI-assisted code review and test prioritization, so that I can catch defects that would normally require a second pair of eyes.

#### Acceptance Criteria

1. THE logitaxAgent project SHALL contain documented evidence (`docs/qa/code-review-diff.md`) of an AI-performed code review on a real pull request diff, referencing the specific PR number or commit hash, and identifying at least 3 issues or improvement suggestions with category (bug, style, performance, or security) for each.
2. THE logitaxAgent project SHALL contain integration tests covering the full simulation flow — input validation, parallel execution (4 years: 2026, 2027, 2030, 2033), aggregation, and result structure verification — where result structure asserts the presence of: tax value under Regime_Atual, tax value under Regime_Novo, Delta_Percentual, data source identifier, and fallback flag for each simulated year.
3. WHEN the integration test suite is executed, THE logitaxAgent project SHALL produce a passing result (exit code 0) for all integration tests covering the simulation flow within 120 seconds.
4. THE logitaxAgent project SHALL contain a test prioritization document (`docs/qa/priorizacao-testes.md`) that ranks at least 3 test scenarios by risk level, justifying the highest-risk scenario based on financial impact (potential monetary loss magnitude) and calculation complexity (number of conditional rules or transition-year dependencies involved).

### Requirement 13: DevOps inteligente com análise de logs por IA

**User Story:** As a responsável pela operação, I want the CI pipeline to detect, explain, and classify failures automatically, so that I do not depend on reading raw logs manually.

#### Acceptance Criteria

1. WHEN a push or pull request is made to the repository, THE logitaxAgent GitHub Actions pipeline SHALL execute lint (ruff), tests (pytest), and build (successful installation of project dependencies and import validation) in sequence.
2. THE logitaxAgent project SHALL include a script (`scripts/analisar_logs_ci.py`) that uses AI to analyze logs from at least two pipeline stages (lint and test) and produce a structured output containing: stage name, pass/fail status, a natural-language explanation of the failure cause (maximum 300 characters per stage), and a severity classification (critical, warning, or info) for each analyzed stage.
3. THE logitaxAgent project SHALL include a script (`scripts/simular_falhas_tool.py`) that simulates at least 3 distinct failure types in the Tool_Transicao (timeout, invalid response, connection refused), executes a minimum of 10 requests per failure type, and outputs the observed anomaly rate (failed requests / total requests) to stdout and to a results file in `docs/devops/`.
4. THE logitaxAgent project SHALL produce a documented risk estimation (`docs/devops/deteccao-anomalia.md`) based on observed failure rates, classifying risk as low (anomaly rate below 5%), medium (5% to 20%), or high (above 20%), and including at least one recommended mitigation action per identified risk level.
5. IF the AI service used by `scripts/analisar_logs_ci.py` is unavailable or returns an error, THEN THE script SHALL output a fallback message indicating that automated analysis is unavailable and exit with a non-zero status code without blocking the pipeline execution.

### Requirement 14: Integração low-code com n8n

**User Story:** As a gestor de frete, I want to receive automatic alerts when a simulation shows a significant tax increase, so that I can act proactively without checking the system manually.

#### Acceptance Criteria

1. WHEN a simulation is approved via Human_Review, THE logitaxAgent SHALL send the result payload to the Webhook_N8n endpoint, including at minimum: Thread_Id, Delta_Percentual, ano de referência, valor_tributo_atual, valor_tributo_novo, and the timestamp of approval.
2. IF the Webhook_N8n call fails or does not respond within 10 seconds, THEN THE logitaxAgent SHALL log the failure as a structured event in the audit trail (containing Thread_Id, HTTP status or timeout indication, and timestamp) and SHALL NOT retry automatically.
3. WHEN the Delta_Percentual in the received payload exceeds the configured threshold (default 15%, configurable between 1% and 100%), THE n8n flow SHALL generate at least one observable notification (email, messaging platform message, or issue creation in a project tracker) containing the Thread_Id and the Delta_Percentual value.
4. THE logitaxAgent SHALL keep all tax calculation logic (delta computation, threshold comparison) within the application; the n8n flow SHALL act only as notification orchestrator and SHALL NOT modify or recalculate tax values.
5. THE logitaxAgent project SHALL include the n8n flow exported as `low-code/n8n-fluxo-alerta.json` with reproduction instructions documented in README.md that contain: prerequisites (n8n version, required credentials), step-by-step import procedure, a sample payload for manual testing, and expected notification output.

### Requirement 15: Documentação de prompts e ciclo de refinamento

**User Story:** As an avaliador do projeto, I want to understand the prompt engineering decisions made during development, so that I can evaluate the developer's iterative approach.

#### Acceptance Criteria

1. THE logitaxAgent project SHALL maintain documented system prompts in `docs/prompts/`, with one file per LLM-using node, where each file contains at minimum: the system prompt text, the behavior rules and restrictions imposed on the LLM, the expected output format, and the list of input variables injected into the prompt.
2. THE logitaxAgent project SHALL configure the LLM model name and endpoint exclusively via environment variables, and the repository SHALL contain a `.env.example` file listing all required LLM-related variable names without secret values.
3. THE logitaxAgent project SHALL document at least one real prompt refinement cycle in `docs/evidencias/ciclo-refinamento.md`, containing: (a) the observed problem with a concrete example of incorrect output, (b) the change applied with a reference to the commit or PR where the prompt was modified, and (c) the measured result expressed as a before/after comparison using an observable metric such as test pass rate, correct citation rate, or reproduction of the failure scenario showing resolution.
