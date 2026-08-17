$repo = "prbretas/projeto-avaliativo-logitaxAgent"
$delay = 15
$maxRetries = 3

function Create-Issue {
    param($title, $labels, $body)
    for ($i = 1; $i -le $maxRetries; $i++) {
        Start-Sleep -Seconds $delay
        $result = gh issue create --repo $repo --title $title --label $labels --body $body 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK: $title" -ForegroundColor Green
            return $true
        }
        Write-Host "  Tentativa $i falhou para: $title" -ForegroundColor Yellow
        Start-Sleep -Seconds (10 * $i)
    }
    Write-Host "  FALHA DEFINITIVA: $title" -ForegroundColor Red
    return $false
}

Write-Host "=== Criando 22 issues restantes ===" -ForegroundColor Cyan

$created = 0; $failed = 0

# 5.11
if (Create-Issue "[5.11] Property test: reclassification counter never exceeds 3" "epic:grafo,property-test" "Property 9. Arquivo: tests/test_properties_stopping.py. Validates: Req 6.3, 6.4. Wave 9.") { $created++ } else { $failed++ }

# 5.12
if (Create-Issue "[5.12] Property test: no re-entry after forced human review" "epic:grafo,property-test" "Property 10. Arquivo: tests/test_properties_stopping.py. Validates: Req 6.5. Wave 9.") { $created++ } else { $failed++ }

# 7.1
if (Create-Issue "[7.1] Implementar indice vetorial ChromaDB e script de ingestao" "epic:rag" "Criar scripts/run_ingestao.py para indexar trechos de LC 214/2025, EC 132/2023 e NTs CT-e. Metadata por chunk. Requirements: 7.1, 7.6. Wave 10.") { $created++ } else { $failed++ }

# 7.2
if (Create-Issue "[7.2] Implementar node retrieve_context" "epic:rag" "Criar src/graph/nodes/retrieve_context.py. Busca vetorial ChromaDB filtrada por cenario. Ate 5 chunks com citacoes. Requirements: 7.1, 7.2, 7.3. Wave 11.") { $created++ } else { $failed++ }

# 7.3
if (Create-Issue "[7.3] Implementar node generate_justification" "epic:rag" "Criar src/graph/nodes/generate_justification.py. Prompt com trechos RAG + resultados. Verificar rates vs Tool. Mismatch: retry 2x, escalar. Requirements: 7.2, 7.4, 7.5. Wave 12.") { $created++ } else { $failed++ }

# 7.4
if (Create-Issue "[7.4] Property test: justification rates match tool rates" "epic:rag,property-test" "Property 11. Arquivo: tests/test_properties_justificativa.py. Validates: Req 7.4. Wave 12.") { $created++ } else { $failed++ }

# 7.5
if (Create-Issue "[7.5] Implementar node human_review com interrupt" "epic:rag" "Criar src/graph/nodes/human_review.py. Interrupt LangGraph. Resumo com valores, delta, fallback. Aprovacao/rejeicao. Timeout 24h. Requirements: 10.1, 10.2, 10.3, 10.5, 10.6. Wave 13.") { $created++ } else { $failed++ }

# 7.6
if (Create-Issue "[7.6] Property test: no export without human approval" "epic:rag,property-test" "Property 16. Arquivo: tests/test_properties_human_review.py. Validates: Req 10.4. Wave 14.") { $created++ } else { $failed++ }

# 7.7
if (Create-Issue "[7.7] Property test: pending review retrieval is idempotent" "epic:rag,property-test" "Property 17. Arquivo: tests/test_properties_human_review.py. Validates: Req 10.6. Wave 14.") { $created++ } else { $failed++ }

# 8.1
if (Create-Issue "[8.1] Implementar SQLite checkpointer para sessao" "epic:persistencia" "Criar src/persistence/checkpointer.py. Persistir estado por thread_id. TTL 72h. Consulta follow-up. Erro para thread_id inexistente. Requirements: 8.1, 8.2, 8.3, 8.4. Wave 10.") { $created++ } else { $failed++ }

# 8.2
if (Create-Issue "[8.2] Property test: session state round-trip" "epic:persistencia,property-test" "Property 12. Arquivo: tests/test_properties_sessao.py. Validates: Req 8.1, 8.2. Wave 11.") { $created++ } else { $failed++ }

# 8.3
if (Create-Issue "[8.3] Property test: unknown thread_id returns error" "epic:persistencia,property-test" "Property 13. Arquivo: tests/test_properties_sessao.py. Validates: Req 8.3. Wave 11.") { $created++ } else { $failed++ }

# 8.4
if (Create-Issue "[8.4] Implementar node export_result e webhook n8n" "epic:persistencia" "Criar src/graph/nodes/export_result.py. Persistir JSON final. Disparar webhook. Timeout 10s, falha: logar sem retry. Requirements: 10.3, 14.1, 14.2. Wave 13.") { $created++ } else { $failed++ }

# 8.5
if (Create-Issue "[8.5] Property test: webhook payload contains required fields" "epic:persistencia,property-test" "Property 19. Arquivo: tests/test_properties_webhook.py. Validates: Req 14.1. Wave 14.") { $created++ } else { $failed++ }

# 9.1
if (Create-Issue "[9.1] Implementar endpoints da API principal" "epic:api" "Criar src/api/main.py com FastAPI. POST /simular, GET /tools/tabela-transicao, POST /review/{thread_id}, GET /observabilidade/{thread_id}. Requirements: 5.1, 10.1, 11.4, 11.5. Wave 15.") { $created++ } else { $failed++ }

# 9.2
if (Create-Issue "[9.2] Implementar sistema de logs estruturados" "epic:api" "Criar src/observability/logger.py. JSON logs por node. Tabela auditoria SQLite. Registrar erros com recovery action. Requirements: 11.1, 11.2, 11.3. Wave 15.") { $created++ } else { $failed++ }

# 9.3
if (Create-Issue "[9.3] Property test: structured logs contain all required fields" "epic:api,property-test" "Property 18. Arquivo: tests/test_properties_observabilidade.py. Validates: Req 11.1. Wave 16.") { $created++ } else { $failed++ }

# 11.1
if (Create-Issue "[11.1] Montar StateGraph completo" "epic:integracao" "Criar src/graph/graph.py. Registrar nodes. Configurar edges completas. Conditional edge route_regime. Interrupt human_review. Requirements: 4.3, 6.1. Wave 17.") { $created++ } else { $failed++ }

# 11.2
if (Create-Issue "[11.2] Implementar testes de integracao end-to-end" "epic:integracao" "Criar tests/test_simulacao_integracao.py. Fluxo completo 4 anos. Verificar campos obrigatorios. Cenario fallback. Tempo max 120s. Requirements: 12.2, 12.3. Wave 18.") { $created++ } else { $failed++ }

# 12.1
if (Create-Issue "[12.1] Criar pipeline GitHub Actions" "epic:devops" "Criar .github/workflows/ci.yml. Lint (ruff), tests (pytest), build. Requirements: 13.1. Wave 19.") { $created++ } else { $failed++ }

# 12.2
if (Create-Issue "[12.2] Criar script analisar_logs_ci.py" "epic:devops" "Analisar logs de 2+ stages com IA. Output estruturado. Fallback se IA indisponivel. Requirements: 13.2, 13.5. Wave 19.") { $created++ } else { $failed++ }

# 12.3
if (Create-Issue "[12.3] Criar script simular_falhas_tool.py" "epic:devops" "Simular 3 tipos de falha. 10+ requests por tipo. Taxa de anomalia. Classificacao risco. Requirements: 13.3, 13.4. Wave 19.") { $created++ } else { $failed++ }

# 12.4
if (Create-Issue "[12.4] Criar fluxo n8n e documentacao" "epic:devops" "Criar low-code/n8n-fluxo-alerta.json. Threshold configuravel. Documentar no README. Requirements: 14.3, 14.4, 14.5. Wave 19.") { $created++ } else { $failed++ }

# 12.5
if (Create-Issue "[12.5] Criar documentacao de prompts e evidencias" "epic:devops" "docs/prompts/ por node LLM. docs/evidencias/ciclo-refinamento.md. Requirements: 15.1, 15.3. Wave 19.") { $created++ } else { $failed++ }

# 12.6
if (Create-Issue "[12.6] Criar documentacao de QA" "epic:devops" "docs/qa/code-review-diff.md e docs/qa/priorizacao-testes.md. Requirements: 12.1, 12.4. Wave 19.") { $created++ } else { $failed++ }

Write-Host ""
Write-Host "=== RESULTADO FINAL ===" -ForegroundColor Cyan
Write-Host "Criadas com sucesso: $created / 24" -ForegroundColor Green
if ($failed -gt 0) { Write-Host "Falharam: $failed" -ForegroundColor Red }
Write-Host "Verifique: https://github.com/prbretas/projeto-avaliativo-logitaxAgent/issues"
