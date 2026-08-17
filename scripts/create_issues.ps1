$repo = "prbretas/projeto-avaliativo-logitaxAgent"
$delay = 6

Write-Host "Criando issues restantes no GitHub..." -ForegroundColor Cyan

$issues = @(
    @{ title = "[5.7] Implementar node simular_ano com fan-out/fan-in"; labels = "epic:grafo"; body = "## Descricao`n- Criar src/graph/nodes/simular_ano.py`n- Implementar fan-out paralelo por anos-marco (2026, 2027, 2030, 2033)`n- Chamar client_transicao + motor de calculo para cada ano`n- Implementar fan-in em agregar_resultados`n- Tratar falha parcial`n`n## Requirements`n3.1, 3.2, 3.3, 3.4, 3.5, 3.6`n`n## Wave`n8" },
    @{ title = "[5.8] Property test: fan-out results are chronologically ordered"; labels = "epic:grafo,property-test"; body = "## Descricao`n- Property 6: Fan-out results chronologically ordered`n- Arquivo: tests/test_properties_fanout.py`n`n## Validates`nRequirements 3.2`n`n## Wave`n9" },
    @{ title = "[5.9] Property test: partial failure preserves successful results"; labels = "epic:grafo,property-test"; body = "## Descricao`n- Property 7: Partial failure preserves successful results`n- Arquivo: tests/test_properties_fanout.py`n`n## Validates`nRequirements 3.5`n`n## Wave`n9" },
    @{ title = "[5.10] Implementar condicao de parada (reclassificacao)"; labels = "epic:grafo"; body = "## Descricao`n- Implementar contador tentativas_reclassificacao no AgentState`n- Incrementar a cada reclassificacao; forcar human_review quando atingir 3`n- Garantir que nao ha re-entry apos forced human_review`n`n## Requirements`n6.1, 6.2, 6.3, 6.4, 6.5`n`n## Wave`n8" },
    @{ title = "[5.11] Property test: reclassification counter never exceeds 3"; labels = "epic:grafo,property-test"; body = "## Descricao`n- Property 9: Reclassification counter never exceeds 3`n- Arquivo: tests/test_properties_stopping.py`n`n## Validates`nRequirements 6.3, 6.4`n`n## Wave`n9" },
    @{ title = "[5.12] Property test: no re-entry after forced human review"; labels = "epic:grafo,property-test"; body = "## Descricao`n- Property 10: No re-entry after forced human review`n- Arquivo: tests/test_properties_stopping.py`n`n## Validates`nRequirements 6.5`n`n## Wave`n9" },
    @{ title = "[7.1] Implementar indice vetorial ChromaDB e script de ingestao"; labels = "epic:rag"; body = "## Descricao`n- Criar scripts/run_ingestao.py para indexar trechos de LC 214/2025, EC 132/2023 e NTs CT-e`n- Cada chunk com metadata: source_law, article_number, applicable_year_range`n- Logar numero de chunks indexados e erros de parsing`n`n## Requirements`n7.1, 7.6`n`n## Wave`n10" },
    @{ title = "[7.2] Implementar node retrieve_context"; labels = "epic:rag"; body = "## Descricao`n- Criar src/graph/nodes/retrieve_context.py`n- Busca vetorial em ChromaDB filtrada por cenario (ano, regime)`n- Retornar ate 5 chunks com citacoes formatadas`n- Tratar caso de zero chunks: prosseguir sem citacoes + warning`n`n## Requirements`n7.1, 7.2, 7.3`n`n## Wave`n11" },
    @{ title = "[7.3] Implementar node generate_justification"; labels = "epic:rag"; body = "## Descricao`n- Criar src/graph/nodes/generate_justification.py`n- Compor prompt com trechos RAG + resultados de calculo`n- Verificar rates citadas vs rates da Tool_Transicao`n- Mismatch: descartar, logar, retry ate 2x, escalar human_review`n- Documentar prompt em docs/prompts/generate_justification.md`n`n## Requirements`n7.2, 7.4, 7.5`n`n## Wave`n12" },
    @{ title = "[7.4] Property test: justification rates match tool rates"; labels = "epic:rag,property-test"; body = "## Descricao`n- Property 11: Justification rates match Tool rates`n- Arquivo: tests/test_properties_justificativa.py`n`n## Validates`nRequirements 7.4`n`n## Wave`n12" },
    @{ title = "[7.5] Implementar node human_review com interrupt"; labels = "epic:rag"; body = "## Descricao`n- Criar src/graph/nodes/human_review.py`n- Implementar interrupt no LangGraph - pausar execucao ate decisao humana`n- Apresentar resumo: valores por regime, delta, flag fallback, justificativa`n- Tratar aprovacao -> export_result; rejeicao -> log + terminar`n- Timeout 24h -> expirar sessao`n- Retrieval idempotente`n`n## Requirements`n10.1, 10.2, 10.3, 10.5, 10.6`n`n## Wave`n13" },
    @{ title = "[7.6] Property test: no export without human approval"; labels = "epic:rag,property-test"; body = "## Descricao`n- Property 16: No export without human approval`n- Arquivo: tests/test_properties_human_review.py`n`n## Validates`nRequirements 10.4`n`n## Wave`n14" },
    @{ title = "[7.7] Property test: pending review retrieval is idempotent"; labels = "epic:rag,property-test"; body = "## Descricao`n- Property 17: Pending review retrieval is idempotent`n- Arquivo: tests/test_properties_human_review.py`n`n## Validates`nRequirements 10.6`n`n## Wave`n14" },
    @{ title = "[8.1] Implementar SQLite checkpointer para sessao"; labels = "epic:persistencia"; body = "## Descricao`n- Criar src/persistence/checkpointer.py`n- Persistir estado por thread_id (input, resultados, justificativa)`n- TTL de 72h com purge automatico`n- Consulta por thread_id para follow-up`n- Erro estruturado para thread_id inexistente`n`n## Requirements`n8.1, 8.2, 8.3, 8.4`n`n## Wave`n10" },
    @{ title = "[8.2] Property test: session state round-trip"; labels = "epic:persistencia,property-test"; body = "## Descricao`n- Property 12: Session state round-trip`n- Arquivo: tests/test_properties_sessao.py`n`n## Validates`nRequirements 8.1, 8.2`n`n## Wave`n11" },
    @{ title = "[8.3] Property test: unknown thread_id returns error"; labels = "epic:persistencia,property-test"; body = "## Descricao`n- Property 13: Unknown Thread_Id returns error`n- Arquivo: tests/test_properties_sessao.py`n`n## Validates`nRequirements 8.3`n`n## Wave`n11" },
    @{ title = "[8.4] Implementar node export_result e webhook n8n"; labels = "epic:persistencia"; body = "## Descricao`n- Criar src/graph/nodes/export_result.py`n- Persistir JSON final do ResultadoConsolidado`n- Disparar webhook para Webhook_N8n com payload`n- Timeout webhook 10s - falha: logar sem retry`n`n## Requirements`n10.3, 14.1, 14.2`n`n## Wave`n13" },
    @{ title = "[8.5] Property test: webhook payload contains required fields"; labels = "epic:persistencia,property-test"; body = "## Descricao`n- Property 19: Webhook payload contains required fields`n- Arquivo: tests/test_properties_webhook.py`n`n## Validates`nRequirements 14.1`n`n## Wave`n14" },
    @{ title = "[9.1] Implementar endpoints da API principal"; labels = "epic:api"; body = "## Descricao`n- Criar src/api/main.py com FastAPI app`n- POST /simular`n- GET /tools/tabela-transicao`n- POST /review/{thread_id}`n- GET /observabilidade/{thread_id}`n`n## Requirements`n5.1, 10.1, 11.4, 11.5`n`n## Wave`n15" },
    @{ title = "[9.2] Implementar sistema de logs estruturados"; labels = "epic:api"; body = "## Descricao`n- Criar src/observability/logger.py`n- JSON logs por node: thread_id, node_name, timestamp ISO 8601, duration_ms, status`n- Tabela auditoria SQLite: decisoes humanas, eventos seguranca, fallback`n- Registrar erros com tipo e acao de recovery`n`n## Requirements`n11.1, 11.2, 11.3`n`n## Wave`n15" },
    @{ title = "[9.3] Property test: structured logs contain all required fields"; labels = "epic:api,property-test"; body = "## Descricao`n- Property 18: Structured logs contain all required fields`n- Arquivo: tests/test_properties_observabilidade.py`n`n## Validates`nRequirements 11.1`n`n## Wave`n16" },
    @{ title = "[11.1] Montar StateGraph completo"; labels = "epic:integracao"; body = "## Descricao`n- Criar src/graph/graph.py`n- Registrar todos os nodes no StateGraph`n- Configurar edges completas do grafo`n- Conditional edge para route_regime`n- Interrupt em human_review`n`n## Requirements`n4.3, 6.1`n`n## Wave`n17" },
    @{ title = "[11.2] Implementar testes de integracao end-to-end"; labels = "epic:integracao"; body = "## Descricao`n- Criar tests/test_simulacao_integracao.py`n- Testar fluxo completo com 4 anos (2026, 2027, 2030, 2033)`n- Verificar campos obrigatorios no resultado`n- Testar cenario com fallback`n- Tempo maximo: 120s`n`n## Requirements`n12.2, 12.3`n`n## Wave`n18" },
    @{ title = "[12.1] Criar pipeline GitHub Actions"; labels = "epic:devops"; body = "## Descricao`n- Criar .github/workflows/ci.yml`n- Executar: lint (ruff), tests (pytest), build (install deps + import validation)`n`n## Requirements`n13.1`n`n## Wave`n19" },
    @{ title = "[12.2] Criar script analisar_logs_ci.py"; labels = "epic:devops"; body = "## Descricao`n- Analisar logs de pelo menos 2 stages (lint e test) com IA`n- Output estruturado: stage_name, pass/fail, explicacao, severidade`n- Fallback se servico de IA indisponivel`n`n## Requirements`n13.2, 13.5`n`n## Wave`n19" },
    @{ title = "[12.3] Criar script simular_falhas_tool.py"; labels = "epic:devops"; body = "## Descricao`n- Simular 3 tipos de falha: timeout, resposta invalida, connection refused`n- Minimo 10 requests por tipo`n- Output: taxa de anomalia para stdout e docs/devops/deteccao-anomalia.md`n- Classificacao de risco: low/medium/high`n`n## Requirements`n13.3, 13.4`n`n## Wave`n19" },
    @{ title = "[12.4] Criar fluxo n8n e documentacao"; labels = "epic:devops"; body = "## Descricao`n- Criar low-code/n8n-fluxo-alerta.json`n- Threshold Delta_Percentual (default 15%, configuravel 1-100%)`n- Documentar no README: pre-requisitos, import, payload, output`n`n## Requirements`n14.3, 14.4, 14.5`n`n## Wave`n19" },
    @{ title = "[12.5] Criar documentacao de prompts e evidencias"; labels = "epic:devops"; body = "## Descricao`n- docs/prompts/ com um arquivo por node LLM`n- Cada arquivo: prompt text, behavior rules, output format, input variables`n- docs/evidencias/ciclo-refinamento.md com: problema, mudanca, resultado`n`n## Requirements`n15.1, 15.3`n`n## Wave`n19" },
    @{ title = "[12.6] Criar documentacao de QA"; labels = "epic:devops"; body = "## Descricao`n- docs/qa/code-review-diff.md com evidencia de code review por IA`n- docs/qa/priorizacao-testes.md com ranking de cenarios por risco`n`n## Requirements`n12.1, 12.4`n`n## Wave`n19" }
)

$created = 0
$failed = 0

foreach ($issue in $issues) {
    Start-Sleep -Seconds $delay
    $result = gh issue create --repo $repo --title $issue.title --label $issue.labels --body $issue.body 2>&1
    if ($LASTEXITCODE -eq 0) {
        $created++
        Write-Host "  OK: $($issue.title)" -ForegroundColor Green
    } else {
        $failed++
        Write-Host "  FALHA: $($issue.title) - $result" -ForegroundColor Red
        # Retry once after longer delay
        Start-Sleep -Seconds 15
        $result = gh issue create --repo $repo --title $issue.title --label $issue.labels --body $issue.body 2>&1
        if ($LASTEXITCODE -eq 0) {
            $failed--
            $created++
            Write-Host "  RETRY OK: $($issue.title)" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "=== RESULTADO ===" -ForegroundColor Cyan
Write-Host "Criadas: $created" -ForegroundColor Green
Write-Host "Falhas: $failed" -ForegroundColor Red
Write-Host "Verifique: https://github.com/prbretas/projeto-avaliativo-logitaxAgent/issues"
