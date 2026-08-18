# Detecção de Anomalias — Tool_Transicao

## Resumo da Simulação de Falhas

Script: `scripts/simular_falhas_tool.py`
Data de execução: 2026-08-17
Requests por tipo: 10

| Tipo de Falha | Requests | Falhas Diretas | Fallback Acionado | Taxa Anomalia | Risco | Mitigação |
|---|---|---|---|---|---|---|
| timeout | 10 | 0 | 10 | 0% | **low** | Monitoramento padrão. Fallback local garante continuidade. |
| invalid_response | 10 | 0 | 10 | 0% | **low** | Monitoramento padrão. Parsing falha mas fallback compensa. |
| connection_refused | 10 | 0 | 10 | 0% | **low** | Monitoramento padrão. Retry + fallback garante 100% disponibilidade. |

## Análise

O sistema demonstra **resiliência total** aos 3 tipos de falha testados graças ao mecanismo de fallback local (`data/tabela_transicao_local.json`).

### Comportamento Observado

1. **Timeout (5s)**: O client tenta 2 retries com backoff exponencial (1s, 2s). Após falha nos 3 attempts, aciona fallback local. Tempo total: ~8s por request.

2. **Resposta Inválida (status 200 mas payload malformado)**: O client detecta que o response não conforma ao schema `TabelaTransicaoResponse`, trata como falha e aciona fallback.

3. **Connection Refused**: O client falha imediatamente no connect, retry 2x, e aciona fallback. Tempo total: ~3s por request.

### Conclusão

- **Taxa de anomalia efetiva: 0%** — nenhuma simulação falha para o usuário final
- **Todas as falhas são recuperadas via fallback local**
- **Flag `fallback_usado=True`** é setada transparentemente no resultado
- **Warning com versão do arquivo** é incluído na resposta

## Classificação de Risco

| Nível | Critério | Status |
|-------|----------|--------|
| **low** (<5%) | Monitoramento padrão | ✅ Atual |
| **medium** (5-20%) | Ativar alertas de observabilidade | N/A |
| **high** (>20%) | Investigar causa raiz, circuit breaker | N/A |

## Estimativa de Tendência

Com base na simulação:
- **Probabilidade de falha total (sem resultado):** ~0% (enquanto fallback local estiver disponível)
- **Risco principal:** Dados do fallback ficarem desatualizados se a legislação mudar sem atualização do JSON local
- **Mitigação recomendada:** Monitorar campo `fallback_usado` nos logs. Se taxa > 20% das requests em produção, investigar disponibilidade do endpoint Tool_Transicao.

## Recomendações

1. Configurar alerta no n8n quando `fallback_usado=True` por mais de 10 requests consecutivas
2. Manter `data/tabela_transicao_local.json` atualizado via `docs/projectsfiles/METODOLOGIA.md`
3. Adicionar health check periódico ao endpoint `/tools/tabela-transicao`
