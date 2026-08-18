# Implementation Plan: Simulador de Impacto IBS/CBS

## Overview

Implementação incremental do logitaxAgent — sistema híbrido agêntico (LangGraph) que simula o impacto financeiro da Reforma Tributária brasileira (IBS/CBS) sobre operações de frete. As tarefas seguem a ordem: estrutura do projeto → modelos de dados → lógica de cálculo → nodes do grafo → integração → observabilidade → segurança → documentação.

## Tasks

- [x] 1. Estrutura do projeto e modelos de dados
  - [x] 1.1 Criar estrutura de diretórios e configuração do projeto
    - Criar `pyproject.toml` com dependências: fastapi, uvicorn, langgraph, pydantic, chromadb, sqlite3, hypothesis, pytest, ruff
    - Criar diretórios: `src/`, `src/graph/`, `src/graph/nodes/`, `src/tools/`, `src/models/`, `src/api/`, `tests/`, `data/`, `scripts/`, `docs/prompts/`, `docs/qa/`, `docs/devops/`, `docs/evidencias/`, `low-code/`
    - Criar `.env.example` com variáveis: LLM_MODEL_NAME, LLM_ENDPOINT, CHROMADB_PATH, SQLITE_PATH, WEBHOOK_N8N_URL, DELTA_THRESHOLD_PCT
    - Criar `conftest.py` com fixtures compartilhadas para pytest
    - _Requirements: 9.4, 15.2_

  - [x] 1.2 Implementar modelos Pydantic (data models)
    - Criar `src/models/operacao.py` com `OperacaoFrete` (validação de modal, UFs, regime, valor_frete, data_referencia, observacoes)
    - Criar `src/models/resultado.py` com `ResultadoAno`, `ResultadoConsolidado`
    - Criar `src/models/estado.py` com `AgentState` (thread_id, tentativas_reclassificacao, resultados_por_ano, trechos_rag, justificativa, aprovado_humano, revisao_manual)
    - Criar `src/models/auditoria.py` com `RegistroAuditoria`
    - Criar `src/models/erro.py` com `ErroEstruturado` (erro, campos_invalidos, thread_id, timestamp)
    - Criar `src/models/tabela_transicao.py` com `TabelaTransicaoResponse`
    - Implementar validadores customizados Pydantic para: UFs válidas, range de valor_frete, range de ano, enums de modal e regime
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.6_

  - [ ]* 1.3 Write property test: valid operations accepted
    - **Property 1: Valid operations are always accepted**
    - Usar Hypothesis strategy `valid_operacao` para gerar operações válidas e verificar que passam validação Pydantic sem erros
    - Arquivo: `tests/test_properties_validation.py`
    - **Validates: Requirements 1.1**

  - [ ]* 1.4 Write property test: invalid inputs produce comprehensive errors
    - **Property 2: Invalid inputs produce comprehensive structured errors**
    - Usar Hypothesis strategies para gerar payloads com campos inválidos e verificar que todos os erros são retornados simultaneamente
    - Arquivo: `tests/test_properties_validation.py`
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**

- [x] 2. Tool de consulta de alíquotas e tabela de transição
  - [x] 2.1 Criar tabela de transição local (JSON)
    - Criar/validar `data/tabela_transicao_local.json` com alíquotas por ano (2026–2033), incluindo: aliquota_cbs_pct, aliquota_ibs_pct, aliquota_icms_pct_da_base, aliquota_combinada_nova_pct, fase, versao, oficial
    - Garantir valores conformes à LC 214/2025: 2026 (CBS 0.9% + IBS 0.1%), 2027–2028 (CBS substituindo PIS/COFINS, ICMS 100%), 2029–2032 (phase-out ICMS 90%/80%/70%/60%), 2033 (ICMS 0%, IBS+CBS plenos)
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 5.1_

  - [x] 2.2 Implementar endpoint Tool_Transicao
    - Criar `src/tools/tabela_transicao.py` com endpoint FastAPI `GET /tools/tabela-transicao`
    - Aceitar parâmetros: ano, uf_origem, uf_destino, regime
    - Validar parâmetros com Pydantic (ano 2026–2033, UFs válidas, regime válido)
    - Retornar HTTP 422 com erro estruturado para parâmetros inválidos
    - Retornar `TabelaTransicaoResponse` com campo `versao`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 2.3 Write property test: tool validation rejects invalid parameters
    - **Property 8: Tool validation rejects invalid parameters**
    - Testar que ano fora de [2026, 2033], UF inválida, ou regime inválido retornam HTTP 422
    - Arquivo: `tests/test_properties_tool.py`
    - **Validates: Requirements 5.2, 5.3, 5.4**

  - [x] 2.4 Implementar client da Tool com retry e fallback
    - Criar `src/tools/client_transicao.py` com função que consulta o endpoint
    - Implementar timeout de 5 segundos, retry 2x com backoff exponencial (1s, 2s)
    - Implementar fallback para `data/tabela_transicao_local.json` quando todas retries falham
    - Setar flag `fallback_usado=True` e incluir warning com versão do arquivo
    - _Requirements: 5.5, 5.6, 5.7_

- [x] 3. Checkpoint — Validar modelos e tool
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Lógica de cálculo tributário
  - [x] 4.1 Implementar motor de cálculo para Regime_Atual
    - Criar `src/graph/nodes/calculo.py` com função que calcula: valor_frete × (PIS 1.65% + COFINS 7.6% + ICMS 12.0%)
    - Arredondamento para 2 casas decimais em valores monetários
    - _Requirements: 2.1_

  - [x] 4.2 Implementar motor de cálculo para Regime_Novo (regular)
    - Calcular tributo novo usando alíquotas da Tabela_Transicao: CBS + IBS + (ICMS × percentual_fase)
    - Aplicar créditos não-cumulativos (lucro_real, lucro_presumido)
    - Arredondamento para 2 casas decimais
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.2_

  - [x] 4.3 Implementar motor de cálculo para Simples Nacional
    - Calcular tributo novo sem créditos (credit=0) conforme regras do Simples
    - _Requirements: 4.1_

  - [x] 4.4 Implementar cálculo de Delta_Percentual
    - Fórmula: ((valor_tributo_novo − valor_tributo_atual) / valor_tributo_atual) × 100
    - Arredondamento para 2 casas decimais
    - _Requirements: 2.6_

  - [ ]* 4.5 Write property test: tax calculation uses correct year-specific formula
    - **Property 3: Tax calculation uses correct year-specific formula**
    - Para qualquer operação válida e ano, verificar que valor_tributo_atual = valor_frete × 21.25% e valor_tributo_novo usa rates da Tabela_Transicao
    - Arquivo: `tests/test_properties_calculo.py`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

  - [ ]* 4.6 Write property test: delta percentual is correctly derived
    - **Property 4: Delta percentual is correctly derived**
    - Verificar que delta = ((novo − atual) / atual) × 100 com 2 casas decimais
    - Arquivo: `tests/test_properties_calculo.py`
    - **Validates: Requirements 2.6**

  - [ ]* 4.7 Write property test: regime routing produces differentiated results
    - **Property 5: Regime routing produces differentiated results**
    - Gerar pares de operações idênticas exceto regime (simples vs lucro_real) e verificar valores diferentes
    - Arquivo: `tests/test_properties_routing.py`
    - **Validates: Requirements 4.1, 4.2, 4.5**

- [x] 5. Nodes do grafo LangGraph
  - [x] 5.1 Implementar node `parse_operacao`
    - Criar `src/graph/nodes/parse_operacao.py`
    - Validar payload JSON contra schema OperacaoFrete
    - Retornar todos os erros de validação em resposta única (fail-fast coletivo)
    - _Requirements: 1.1, 1.7, 1.8_

  - [x] 5.2 Implementar node `sanitize_input`
    - Criar `src/graph/nodes/sanitize_input.py`
    - Encapsular campo `observacoes` em bloco delimitado "UNTRUSTED_USER_DATA"
    - Truncar conteúdo para máximo 500 caracteres
    - Detectar padrões de prompt injection e logar evento de segurança
    - Implementar timeout de 3 segundos — bloquear operação se falhar
    - _Requirements: 9.1, 9.2, 9.5_

  - [ ]* 5.3 Write property test: sanitizer wraps and truncates
    - **Property 14: Sanitizer wraps and truncates**
    - Verificar que qualquer string em observacoes é encapsulada em "UNTRUSTED_USER_DATA" e limitada a 500 chars
    - Arquivo: `tests/test_properties_seguranca.py`
    - **Validates: Requirements 9.1**

  - [ ]* 5.4 Write property test: prompt injection does not alter tax results
    - **Property 15: Prompt injection does not alter tax results**
    - Verificar que operações com padrões de injection retornam mesmos valores de tributo que operações com texto benigno
    - Arquivo: `tests/test_properties_seguranca.py`
    - **Validates: Requirements 9.2**

  - [x] 5.5 Implementar node `route_regime`
    - Criar `src/graph/nodes/route_regime.py`
    - Implementar conditional edge no StateGraph baseado em `regime_tributario`
    - Rotear para `simular_regime_hibrido_simples` ou `simular_regime_regular`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 5.6 Implementar nodes `simular_regime_regular` e `simular_regime_hibrido_simples`
    - Criar `src/graph/nodes/simular_regime.py`
    - `simular_regime_regular`: preparar parâmetros com créditos plenos
    - `simular_regime_hibrido_simples`: preparar parâmetros com credit=0
    - _Requirements: 4.1, 4.2_

  - [x] 5.7 Implementar node `simular_ano` com fan-out/fan-in
    - Criar `src/graph/nodes/simular_ano.py`
    - Implementar fan-out paralelo por anos-marco (2026, 2027, 2030, 2033) usando LangGraph parallel nodes
    - Chamar client_transicao + motor de cálculo para cada ano
    - Implementar fan-in em `agregar_resultados` — consolidar ResultadoAno em lista ordenada cronologicamente
    - Tratar falha parcial: retornar resultados bem-sucedidos + indicar anos com falha
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 5.8 Write property test: fan-out results are chronologically ordered
    - **Property 6: Fan-out results are chronologically ordered**
    - Verificar que resultados consolidados são ordenados por ano ascendente
    - Arquivo: `tests/test_properties_fanout.py`
    - **Validates: Requirements 3.2**

  - [ ]* 5.9 Write property test: partial failure preserves successful results
    - **Property 7: Partial failure preserves successful results**
    - Simular falha em subset de anos e verificar que resultados bem-sucedidos são preservados
    - Arquivo: `tests/test_properties_fanout.py`
    - **Validates: Requirements 3.5**

  - [x] 5.10 Implementar condição de parada (reclassificação)
    - Implementar contador `tentativas_reclassificacao` no AgentState
    - Incrementar a cada reclassificação; forçar human_review quando atingir 3
    - Garantir que não há re-entry após forced human_review
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 5.11 Write property test: reclassification counter never exceeds 3
    - **Property 9: Reclassification counter never exceeds 3**
    - Verificar que tentativas_reclassificacao nunca excede 3 e força human_review
    - Arquivo: `tests/test_properties_stopping.py`
    - **Validates: Requirements 6.3, 6.4**

  - [ ]* 5.12 Write property test: no re-entry after forced human review
    - **Property 10: No re-entry after forced human review**
    - Verificar que após revisao_manual=true, não há retorno ao loop de simulação
    - Arquivo: `tests/test_properties_stopping.py`
    - **Validates: Requirements 6.5**

- [x] 6. Checkpoint — Validar grafo e cálculos
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. RAG, justificativa e human review
  - [x] 7.1 Implementar índice vetorial ChromaDB e script de ingestão
    - Criar `scripts/run_ingestao.py` para indexar trechos de LC 214/2025, EC 132/2023 e NTs CT-e
    - Cada chunk com metadata: source_law, article_number, applicable_year_range
    - Logar número de chunks indexados e erros de parsing
    - _Requirements: 7.1, 7.6_

  - [x] 7.2 Implementar node `retrieve_context`
    - Criar `src/graph/nodes/retrieve_context.py`
    - Busca vetorial em ChromaDB filtrada por cenário (ano, regime)
    - Retornar até 5 chunks com citações formatadas (ex: "art. 343, LC 214/2025")
    - Tratar caso de zero chunks: prosseguir sem citações + warning
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 7.3 Implementar node `generate_justification`
    - Criar `src/graph/nodes/generate_justification.py`
    - Compor prompt com trechos RAG + resultados de cálculo
    - Verificar que rates citadas no texto correspondem às rates da Tool_Transicao
    - Em caso de mismatch: descartar, logar, retry até 2x, escalar para human_review
    - Documentar prompt em `docs/prompts/generate_justification.md`
    - _Requirements: 7.2, 7.4, 7.5_

  - [ ]* 7.4 Write property test: justification rates match tool rates
    - **Property 11: Justification rates match Tool rates**
    - Verificar que rates citadas na justificativa correspondem exatamente às rates retornadas pela Tool
    - Arquivo: `tests/test_properties_justificativa.py`
    - **Validates: Requirements 7.4**

  - [x] 7.5 Implementar node `human_review` com interrupt
    - Criar `src/graph/nodes/human_review.py`
    - Implementar interrupt no LangGraph — pausar execução até decisão humana
    - Apresentar resumo: valores por regime, delta, flag fallback, justificativa
    - Tratar aprovação → export_result; rejeição → log + terminar
    - Implementar timeout de 24h → expirar sessão
    - Retrieval idempotente (consultar sem alterar estado)
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_

  - [ ]* 7.6 Write property test: no export without human approval
    - **Property 16: No export without human approval**
    - Verificar que export_result nunca executa sem aprovado_humano=true
    - Arquivo: `tests/test_properties_human_review.py`
    - **Validates: Requirements 10.4**

  - [ ]* 7.7 Write property test: pending review retrieval is idempotent
    - **Property 17: Pending review retrieval is idempotent**
    - Verificar que consultas repetidas ao resumo não alteram estado pendente
    - Arquivo: `tests/test_properties_human_review.py`
    - **Validates: Requirements 10.6**

- [x] 8. Persistência, sessão e exportação
  - [x] 8.1 Implementar SQLite checkpointer para sessão
    - Criar `src/persistence/checkpointer.py`
    - Persistir estado de simulação por thread_id (input, resultados, justificativa)
    - Implementar TTL de 72h com purge automático
    - Implementar consulta por thread_id para follow-up
    - Retornar erro estruturado para thread_id inexistente
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 8.2 Write property test: session state round-trip
    - **Property 12: Session state round-trip**
    - Verificar que estado persistido e recuperado é idêntico ao original
    - Arquivo: `tests/test_properties_sessao.py`
    - **Validates: Requirements 8.1, 8.2**

  - [ ]* 8.3 Write property test: unknown thread_id returns error
    - **Property 13: Unknown Thread_Id returns error**
    - Verificar que thread_id sem estado retorna erro pedindo input completo
    - Arquivo: `tests/test_properties_sessao.py`
    - **Validates: Requirements 8.3**

  - [x] 8.4 Implementar node `export_result` e webhook n8n
    - Criar `src/graph/nodes/export_result.py`
    - Persistir JSON final do ResultadoConsolidado
    - Disparar webhook para Webhook_N8n com payload: thread_id, delta_percentual, ano, valores, timestamp
    - Timeout webhook 10s — em caso de falha, logar na auditoria sem retry
    - _Requirements: 10.3, 14.1, 14.2_

  - [ ]* 8.5 Write property test: webhook payload contains required fields
    - **Property 19: Webhook payload contains required fields**
    - Verificar que payload contém: Thread_Id, Delta_Percentual, ano, valor_tributo_atual, valor_tributo_novo, timestamp
    - Arquivo: `tests/test_properties_webhook.py`
    - **Validates: Requirements 14.1**

- [x] 9. API FastAPI e observabilidade
  - [x] 9.1 Implementar endpoints da API principal
    - Criar `src/api/main.py` com FastAPI app
    - `POST /simular` — submete operação de frete para simulação
    - `GET /tools/tabela-transicao` — consulta alíquotas (wiring com tool)
    - `POST /review/{thread_id}` — aprova ou rejeita resultado pendente
    - `GET /observabilidade/{thread_id}` — retorna timeline completa de execução
    - _Requirements: 5.1, 10.1, 11.4, 11.5_

  - [x] 9.2 Implementar sistema de logs estruturados
    - Criar `src/observability/logger.py`
    - Emitir JSON logs por node: thread_id, node_name, timestamp ISO 8601, duration_ms, status
    - Implementar tabela de auditoria SQLite: decisões humanas, eventos de segurança, fallback
    - Registrar erros com tipo e ação de recovery (retry, fallback, escalation)
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ]* 9.3 Write property test: structured logs contain all required fields
    - **Property 18: Structured logs contain all required fields**
    - Verificar que cada log contém: Thread_Id, node name, ISO 8601 timestamp, duration_ms ≥ 0, status
    - Arquivo: `tests/test_properties_observabilidade.py`
    - **Validates: Requirements 11.1**

- [x] 10. Checkpoint — Validar API e observabilidade
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Montagem do grafo LangGraph e integração end-to-end
  - [x] 11.1 Montar StateGraph completo
    - Criar `src/graph/graph.py`
    - Registrar todos os nodes no StateGraph
    - Configurar edges: parse → sanitize → route_regime → simular_regime_* → fan-out → agregar → retrieve_context → generate_justification → human_review → export_result
    - Configurar conditional edge para route_regime
    - Configurar interrupt em human_review
    - _Requirements: 4.3, 6.1_

  - [x] 11.2 Implementar testes de integração end-to-end
    - Criar `tests/test_simulacao_integracao.py`
    - Testar fluxo completo: validação → cálculo paralelo (4 anos: 2026, 2027, 2030, 2033) → agregação → estrutura do resultado
    - Verificar presença de: valor_tributo_atual, valor_tributo_novo, delta_percentual, fonte, fallback_flag por ano
    - Testar cenário com fallback quando tool indisponível
    - Tempo máximo: 120s
    - _Requirements: 12.2, 12.3_

- [x] 12. Scripts DevOps e documentação
  - [x] 12.1 Criar pipeline GitHub Actions
    - Criar `.github/workflows/ci.yml`
    - Executar em sequência: lint (ruff), tests (pytest), build (install deps + import validation)
    - _Requirements: 13.1_

  - [x] 12.2 Criar script `scripts/analisar_logs_ci.py`
    - Analisar logs de pelo menos 2 stages (lint e test) com IA
    - Output estruturado: stage_name, pass/fail, explicação (max 300 chars), severidade (critical/warning/info)
    - Fallback se serviço de IA indisponível: mensagem + exit code não-zero sem bloquear pipeline
    - _Requirements: 13.2, 13.5_

  - [x] 12.3 Criar script `scripts/simular_falhas_tool.py`
    - Simular 3 tipos de falha na Tool_Transicao: timeout, resposta inválida, connection refused
    - Mínimo 10 requests por tipo de falha
    - Output: taxa de anomalia (failed/total) para stdout e `docs/devops/deteccao-anomalia.md`
    - Classificação de risco: low (<5%), medium (5–20%), high (>20%) com ação de mitigação
    - _Requirements: 13.3, 13.4_

  - [x] 12.4 Criar fluxo n8n e documentação
    - Criar `low-code/n8n-fluxo-alerta.json` com fluxo exportado
    - Configurar threshold Delta_Percentual (default 15%, configurável 1–100%)
    - Documentar no README: pré-requisitos, import step-by-step, payload exemplo, output esperado
    - _Requirements: 14.3, 14.4, 14.5_

  - [x] 12.5 Criar documentação de prompts e evidências
    - Criar docs em `docs/prompts/` com um arquivo por node LLM (generate_justification, route_intencao)
    - Cada arquivo: prompt text, behavior rules, output format, input variables
    - Criar `docs/evidencias/ciclo-refinamento.md` com: problema observado, mudança aplicada (ref commit/PR), resultado medido (before/after)
    - _Requirements: 15.1, 15.3_

  - [x] 12.6 Criar documentação de QA
    - Criar `docs/qa/code-review-diff.md` com evidência de code review por IA em PR real (≥3 issues: bug/style/performance/security)
    - Criar `docs/qa/priorizacao-testes.md` com ranking de ≥3 cenários por risco (impacto financeiro + complexidade de cálculo)
    - _Requirements: 12.1, 12.4_

- [x] 13. Final checkpoint — Validação completa
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (19 properties from design)
- Unit tests validate specific examples and edge cases
- All code uses Python with FastAPI, LangGraph, Pydantic, Hypothesis, pytest
- The LLM is NEVER used for tax calculation — only for justification generation and intent routing

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["1.3", "1.4", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3"] },
    { "id": 5, "tasks": ["4.4", "4.5", "4.6", "4.7"] },
    { "id": 6, "tasks": ["5.1", "5.2", "5.5"] },
    { "id": 7, "tasks": ["5.3", "5.4", "5.6"] },
    { "id": 8, "tasks": ["5.7", "5.10"] },
    { "id": 9, "tasks": ["5.8", "5.9", "5.11", "5.12"] },
    { "id": 10, "tasks": ["7.1", "8.1"] },
    { "id": 11, "tasks": ["7.2", "8.2", "8.3"] },
    { "id": 12, "tasks": ["7.3", "7.4"] },
    { "id": 13, "tasks": ["7.5", "8.4"] },
    { "id": 14, "tasks": ["7.6", "7.7", "8.5"] },
    { "id": 15, "tasks": ["9.1", "9.2"] },
    { "id": 16, "tasks": ["9.3"] },
    { "id": 17, "tasks": ["11.1"] },
    { "id": 18, "tasks": ["11.2"] },
    { "id": 19, "tasks": ["12.1", "12.2", "12.3", "12.4", "12.5", "12.6"] }
  ]
}
```
