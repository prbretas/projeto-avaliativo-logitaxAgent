#!/bin/bash
# Script para criar as issues restantes no GitHub
# Issues 1.1-5.6 ja foram criadas. Este script cria de 5.7 em diante.

REPO="prbretas/projeto-avaliativo-logitaxAgent"
DELAY=5  # segundos entre cada issue para evitar 503

echo "Criando issues restantes no GitHub..."

# 5.7
sleep $DELAY
gh issue create --repo "$REPO" --title "[5.7] Implementar node simular_ano com fan-out/fan-in" --label "epic:grafo" --body "## Descricao
- Criar src/graph/nodes/simular_ano.py
- Implementar fan-out paralelo por anos-marco (2026, 2027, 2030, 2033) usando LangGraph parallel nodes
- Chamar client_transicao + motor de calculo para cada ano
- Implementar fan-in em agregar_resultados - consolidar ResultadoAno em lista ordenada cronologicamente
- Tratar falha parcial: retornar resultados bem-sucedidos + indicar anos com falha

## Requirements
3.1, 3.2, 3.3, 3.4, 3.5, 3.6

## Wave
8 (depende de 5.5, 5.6)"
echo ">> 5.7 criada"

# 5.8
sleep $DELAY
gh issue create --repo "$REPO" --title "[5.8] Property test: fan-out results are chronologically ordered" --label "epic:grafo,property-test" --body "## Descricao
- Property 6: Fan-out results are chronologically ordered
- Verificar que resultados consolidados sao ordenados por ano ascendente
- Arquivo: tests/test_properties_fanout.py

## Validates
Requirements 3.2

## Wave
9 (depende de 5.7)

## Nota
Task opcional (property test)"
echo ">> 5.8 criada"

# 5.9
sleep $DELAY
gh issue create --repo "$REPO" --title "[5.9] Property test: partial failure preserves successful results" --label "epic:grafo,property-test" --body "## Descricao
- Property 7: Partial failure preserves successful results
- Simular falha em subset de anos e verificar que resultados bem-sucedidos sao preservados
- Arquivo: tests/test_properties_fanout.py

## Validates
Requirements 3.5

## Wave
9 (depende de 5.7)

## Nota
Task opcional (property test)"
echo ">> 5.9 criada"

# 5.10
sleep $DELAY
gh issue create --repo "$REPO" --title "[5.10] Implementar condicao de parada (reclassificacao)" --label "epic:grafo" --body "## Descricao
- Implementar contador tentativas_reclassificacao no AgentState
- Incrementar a cada reclassificacao; forcar human_review quando atingir 3
- Garantir que nao ha re-entry apos forced human_review

## Requirements
6.1, 6.2, 6.3, 6.4, 6.5

## Wave
8 (depende de 5.5, 5.6)"
echo ">> 5.10 criada"

# 5.11
sleep $DELAY
gh issue create --repo "$REPO" --title "[5.11] Property test: reclassification counter never exceeds 3" --label "epic:grafo,property-test" --body "## Descricao
- Property 9: Reclassification counter never exceeds 3
- Verificar que tentativas_reclassificacao nunca excede 3 e forca human_review
- Arquivo: tests/test_properties_stopping.py

## Validates
Requirements 6.3, 6.4

## Wave
9 (depende de 5.10)

## Nota
Task opcional (property test)"
echo ">> 5.11 criada"

# 5.12
sleep $DELAY
gh issue create --repo "$REPO" --title "[5.12] Property test: no re-entry after forced human review" --label "epic:grafo,property-test" --body "## Descricao
- Property 10: No re-entry after forced human review
- Verificar que apos revisao_manual=true, nao ha retorno ao loop de simulacao
- Arquivo: tests/test_properties_stopping.py

## Validates
Requirements 6.5

## Wave
9 (depende de 5.10)

## Nota
Task opcional (property test)"
echo ">> 5.12 criada"

# 7.1
sleep $DELAY
gh issue create --repo "$REPO" --title "[7.1] Implementar indice vetorial ChromaDB e script de ingestao" --label "epic:rag" --body "## Descricao
- Criar scripts/run_ingestao.py para indexar trechos de LC 214/2025, EC 132/2023 e NTs CT-e
- Cada chunk com metadata: source_law, article_number, applicable_year_range
- Logar numero de chunks indexados e erros de parsing

## Requirements
7.1, 7.6

## Wave
10"
echo ">> 7.1 criada"

# 7.2
sleep $DELAY
gh issue create --repo "$REPO" --title "[7.2] Implementar node retrieve_context" --label "epic:rag" --body "## Descricao
- Criar src/graph/nodes/retrieve_context.py
- Busca vetorial em ChromaDB filtrada por cenario (ano, regime)
- Retornar ate 5 chunks com citacoes formatadas (ex: art. 343, LC 214/2025)
- Tratar caso de zero chunks: prosseguir sem citacoes + warning

## Requirements
7.1, 7.2, 7.3

## Wave
11 (depende de 7.1)"
echo ">> 7.2 criada"

# 7.3
sleep $DELAY
gh issue create --repo "$REPO" --title "[7.3] Implementar node generate_justification" --label "epic:rag" --body "## Descricao
- Criar src/graph/nodes/generate_justification.py
- Compor prompt com trechos RAG + resultados de calculo
- Verificar que rates citadas no texto correspondem as rates da Tool_Transicao
- Em caso de mismatch: descartar, logar, retry ate 2x, escalar para human_review
- Documentar prompt em docs/prompts/generate_justification.md

## Requirements
7.2, 7.4, 7.5

## Wave
12 (depende de 7.2)"
echo ">> 7.3 criada"

# 7.4
sleep $DELAY
gh issue create --repo "$REPO" --title "[7.4] Property test: justification rates match tool rates" --label "epic:rag,property-test" --body "## Descricao
- Property 11: Justification rates match Tool rates
- Verificar que rates citadas na justificativa correspondem exatamente as rates retornadas pela Tool
- Arquivo: tests/test_properties_justificativa.py

## Validates
Requirements 7.4

## Wave
12 (depende de 7.2)

## Nota
Task opcional (property test)"
echo ">> 7.4 criada"

# 7.5
sleep $DELAY
gh issue create --repo "$REPO" --title "[7.5] Implementar node human_review com interrupt" --label "epic:rag" --body "## Descricao
- Criar src/graph/nodes/human_review.py
- Implementar interrupt no LangGraph - pausar execucao ate decisao humana
- Apresentar resumo: valores por regime, delta, flag fallback, justificativa
- Tratar aprovacao -> export_result; rejeicao -> log + terminar
- Implementar timeout de 24h -> expirar sessao
- Retrieval idempotente (consultar sem alterar estado)

## Requirements
10.1, 10.2, 10.3, 10.5, 10.6

## Wave
13 (depende de 7.3)"
echo ">> 7.5 criada"

# 7.6
sleep $DELAY
gh issue create --repo "$REPO" --title "[7.6] Property test: no export without human approval" --label "epic:rag,property-test" --body "## Descricao
- Property 16: No export without human approval
- Verificar que export_result nunca executa sem aprovado_humano=true
- Arquivo: tests/test_properties_human_review.py

## Validates
Requirements 10.4

## Wave
14 (depende de 7.5)

## Nota
Task opcional (property test)"
echo ">> 7.6 criada"

# 7.7
sleep $DELAY
gh issue create --repo "$REPO" --title "[7.7] Property test: pending review retrieval is idempotent" --label "epic:rag,property-test" --body "## Descricao
- Property 17: Pending review retrieval is idempotent
- Verificar que consultas repetidas ao resumo nao alteram estado pendente
- Arquivo: tests/test_properties_human_review.py

## Validates
Requirements 10.6

## Wave
14 (depende de 7.5)

## Nota
Task opcional (property test)"
echo ">> 7.7 criada"

# 8.1
sleep $DELAY
gh issue create --repo "$REPO" --title "[8.1] Implementar SQLite checkpointer para sessao" --label "epic:persistencia" --body "## Descricao
- Criar src/persistence/checkpointer.py
- Persistir estado de simulacao por thread_id (input, resultados, justificativa)
- Implementar TTL de 72h com purge automatico
- Implementar consulta por thread_id para follow-up
- Retornar erro estruturado para thread_id inexistente

## Requirements
8.1, 8.2, 8.3, 8.4

## Wave
10"
echo ">> 8.1 criada"

# 8.2
sleep $DELAY
gh issue create --repo "$REPO" --title "[8.2] Property test: session state round-trip" --label "epic:persistencia,property-test" --body "## Descricao
- Property 12: Session state round-trip
- Verificar que estado persistido e recuperado e identico ao original
- Arquivo: tests/test_properties_sessao.py

## Validates
Requirements 8.1, 8.2

## Wave
11 (depende de 8.1)

## Nota
Task opcional (property test)"
echo ">> 8.2 criada"

# 8.3
sleep $DELAY
gh issue create --repo "$REPO" --title "[8.3] Property test: unknown thread_id returns error" --label "epic:persistencia,property-test" --body "## Descricao
- Property 13: Unknown Thread_Id returns error
- Verificar que thread_id sem estado retorna erro pedindo input completo
- Arquivo: tests/test_properties_sessao.py

## Validates
Requirements 8.3

## Wave
11 (depende de 8.1)

## Nota
Task opcional (property test)"
echo ">> 8.3 criada"

# 8.4
sleep $DELAY
gh issue create --repo "$REPO" --title "[8.4] Implementar node export_result e webhook n8n" --label "epic:persistencia" --body "## Descricao
- Criar src/graph/nodes/export_result.py
- Persistir JSON final do ResultadoConsolidado
- Disparar webhook para Webhook_N8n com payload: thread_id, delta_percentual, ano, valores, timestamp
- Timeout webhook 10s - em caso de falha, logar na auditoria sem retry

## Requirements
10.3, 14.1, 14.2

## Wave
13 (depende de 8.1)"
echo ">> 8.4 criada"

# 8.5
sleep $DELAY
gh issue create --repo "$REPO" --title "[8.5] Property test: webhook payload contains required fields" --label "epic:persistencia,property-test" --body "## Descricao
- Property 19: Webhook payload contains required fields
- Verificar que payload contem: Thread_Id, Delta_Percentual, ano, valor_tributo_atual, valor_tributo_novo, timestamp
- Arquivo: tests/test_properties_webhook.py

## Validates
Requirements 14.1

## Wave
14 (depende de 8.4)

## Nota
Task opcional (property test)"
echo ">> 8.5 criada"

# 9.1
sleep $DELAY
gh issue create --repo "$REPO" --title "[9.1] Implementar endpoints da API principal" --label "epic:api" --body "## Descricao
- Criar src/api/main.py com FastAPI app
- POST /simular - submete operacao de frete para simulacao
- GET /tools/tabela-transicao - consulta aliquotas (wiring com tool)
- POST /review/{thread_id} - aprova ou rejeita resultado pendente
- GET /observabilidade/{thread_id} - retorna timeline completa de execucao

## Requirements
5.1, 10.1, 11.4, 11.5

## Wave
15"
echo ">> 9.1 criada"

# 9.2
sleep $DELAY
gh issue create --repo "$REPO" --title "[9.2] Implementar sistema de logs estruturados" --label "epic:api" --body "## Descricao
- Criar src/observability/logger.py
- Emitir JSON logs por node: thread_id, node_name, timestamp ISO 8601, duration_ms, status
- Implementar tabela de auditoria SQLite: decisoes humanas, eventos de seguranca, fallback
- Registrar erros com tipo e acao de recovery (retry, fallback, escalation)

## Requirements
11.1, 11.2, 11.3

## Wave
15"
echo ">> 9.2 criada"

# 9.3
sleep $DELAY
gh issue create --repo "$REPO" --title "[9.3] Property test: structured logs contain all required fields" --label "epic:api,property-test" --body "## Descricao
- Property 18: Structured logs contain all required fields
- Verificar que cada log contem: Thread_Id, node name, ISO 8601 timestamp, duration_ms >= 0, status
- Arquivo: tests/test_properties_observabilidade.py

## Validates
Requirements 11.1

## Wave
16 (depende de 9.2)

## Nota
Task opcional (property test)"
echo ">> 9.3 criada"

# 11.1
sleep $DELAY
gh issue create --repo "$REPO" --title "[11.1] Montar StateGraph completo" --label "epic:integracao" --body "## Descricao
- Criar src/graph/graph.py
- Registrar todos os nodes no StateGraph
- Configurar edges: parse -> sanitize -> route_regime -> simular_regime_* -> fan-out -> agregar -> retrieve_context -> generate_justification -> human_review -> export_result
- Configurar conditional edge para route_regime
- Configurar interrupt em human_review

## Requirements
4.3, 6.1

## Wave
17"
echo ">> 11.1 criada"

# 11.2
sleep $DELAY
gh issue create --repo "$REPO" --title "[11.2] Implementar testes de integracao end-to-end" --label "epic:integracao" --body "## Descricao
- Criar tests/test_simulacao_integracao.py
- Testar fluxo completo: validacao -> calculo paralelo (4 anos: 2026, 2027, 2030, 2033) -> agregacao -> estrutura do resultado
- Verificar presenca de: valor_tributo_atual, valor_tributo_novo, delta_percentual, fonte, fallback_flag por ano
- Testar cenario com fallback quando tool indisponivel
- Tempo maximo: 120s

## Requirements
12.2, 12.3

## Wave
18 (depende de 11.1)"
echo ">> 11.2 criada"

# 12.1
sleep $DELAY
gh issue create --repo "$REPO" --title "[12.1] Criar pipeline GitHub Actions" --label "epic:devops" --body "## Descricao
- Criar .github/workflows/ci.yml
- Executar em sequencia: lint (ruff), tests (pytest), build (install deps + import validation)

## Requirements
13.1

## Wave
19"
echo ">> 12.1 criada"

# 12.2
sleep $DELAY
gh issue create --repo "$REPO" --title "[12.2] Criar script analisar_logs_ci.py" --label "epic:devops" --body "## Descricao
- Analisar logs de pelo menos 2 stages (lint e test) com IA
- Output estruturado: stage_name, pass/fail, explicacao (max 300 chars), severidade (critical/warning/info)
- Fallback se servico de IA indisponivel: mensagem + exit code nao-zero sem bloquear pipeline

## Requirements
13.2, 13.5

## Wave
19"
echo ">> 12.2 criada"

# 12.3
sleep $DELAY
gh issue create --repo "$REPO" --title "[12.3] Criar script simular_falhas_tool.py" --label "epic:devops" --body "## Descricao
- Simular 3 tipos de falha na Tool_Transicao: timeout, resposta invalida, connection refused
- Minimo 10 requests por tipo de falha
- Output: taxa de anomalia (failed/total) para stdout e docs/devops/deteccao-anomalia.md
- Classificacao de risco: low (<5%), medium (5-20%), high (>20%) com acao de mitigacao

## Requirements
13.3, 13.4

## Wave
19"
echo ">> 12.3 criada"

# 12.4
sleep $DELAY
gh issue create --repo "$REPO" --title "[12.4] Criar fluxo n8n e documentacao" --label "epic:devops" --body "## Descricao
- Criar low-code/n8n-fluxo-alerta.json com fluxo exportado
- Configurar threshold Delta_Percentual (default 15%, configuravel 1-100%)
- Documentar no README: pre-requisitos, import step-by-step, payload exemplo, output esperado

## Requirements
14.3, 14.4, 14.5

## Wave
19"
echo ">> 12.4 criada"

# 12.5
sleep $DELAY
gh issue create --repo "$REPO" --title "[12.5] Criar documentacao de prompts e evidencias" --label "epic:devops" --body "## Descricao
- Criar docs em docs/prompts/ com um arquivo por node LLM (generate_justification, route_intencao)
- Cada arquivo: prompt text, behavior rules, output format, input variables
- Criar docs/evidencias/ciclo-refinamento.md com: problema observado, mudanca aplicada (ref commit/PR), resultado medido (before/after)

## Requirements
15.1, 15.3

## Wave
19"
echo ">> 12.5 criada"

# 12.6
sleep $DELAY
gh issue create --repo "$REPO" --title "[12.6] Criar documentacao de QA" --label "epic:devops" --body "## Descricao
- Criar docs/qa/code-review-diff.md com evidencia de code review por IA em PR real (>=3 issues: bug/style/performance/security)
- Criar docs/qa/priorizacao-testes.md com ranking de >=3 cenarios por risco (impacto financeiro + complexidade de calculo)

## Requirements
12.1, 12.4

## Wave
19"
echo ">> 12.6 criada"

echo ""
echo "=== TODAS AS ISSUES RESTANTES FORAM CRIADAS ==="
echo "Verifique em: https://github.com/prbretas/projeto-avaliativo-logitaxAgent/issues"
