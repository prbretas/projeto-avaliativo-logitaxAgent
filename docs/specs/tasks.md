# Implementation Plan — Simulador de Impacto Financeiro IBS/CBS no Frete

Cada task referencia os requisitos do `requirements.md`. Marque com `[x]` no Kiro conforme
for concluindo. Sugestão: uma branch `feature/*` por bloco (ver `ROADMAP`/`5.4` do
projeto original) e um card no GitHub Project por task.

- [ ] 1. Preparar base do repositório para o M2.2
  - Criar branch `develop` a partir da `main` (se ainda não existir)
  - Criar `.kiro/specs/simulador-impacto-ibs-cbs/` com este spec
  - Atualizar `ROADMAP.md` referenciando o escopo do M2.2
  - _Requirements: contexto geral_

- [ ] 2. Modelar o novo `AgentState` e schemas
  - [ ] 2.1 Criar `OperacaoFrete`, `ResultadoAno`, `AgentState` em `src/schemas/agent_state.py`
  - [ ] 2.2 Escrever testes unitários de validação Pydantic (UF inválida, frete ≤ 0, ano fora
        de 2026–2033)
  - _Requirements: 1.1, 1.5, 2.1_

- [ ] 3. Node `sanitize_input` (defesa contra prompt injection)
  - [ ] 3.1 Implementar função que isola `observacoes` em bloco delimitado e rotulado como
        dado não confiável antes de qualquer uso em prompt
  - [ ] 3.2 Escrever teste `test_prompt_injection.py` com o cenário adversarial descrito no
        design (Seção 5)
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 4. Node `route_regime` (ramificação condicional)
  - [ ] 4.1 Implementar roteamento Simples Nacional x regime regular
  - [ ] 4.2 Implementar `simular_regime_hibrido_simples` com regras de creditamento distintas
  - _Requirements: 2.3_

- [ ] 5. Tool `consultar_tabela_transicao`
  - [ ] 5.1 Criar `data/tabela_transicao_local.json` com alíquotas por ano (2026 = 1%
        combinado conforme LC 214/2025 arts. 343/346/348; anos seguintes com progressão
        documentada nas fontes)
  - [ ] 5.2 Implementar endpoint `GET /tools/tabela-transicao` com validação Pydantic e
        resposta HTTP 422 em caso de parâmetro inválido
  - [ ] 5.3 Implementar client com timeout, retry (2x) e fallback para o JSON local
  - [ ] 5.4 Testes: sucesso, timeout com fallback, parâmetro inválido
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 6. Fan-out/fan-in de simulação paralela por ano
  - [ ] 6.1 Implementar node `simular_ano` (chamado em paralelo pelo LangGraph para
        2026/2027/2030/2033, ou para o ano único se informado)
  - [ ] 6.2 Implementar `agregar_resultados` (fan-in) consolidando `resultados_por_ano`
  - [ ] 6.3 Implementar contador `tentativas_reclassificacao` com corte em 3 tentativas →
        `revisao_manual=True`
  - [ ] 6.4 Teste de integração cobrindo os 4 anos em paralelo e a agregação
  - _Requirements: 1.2, 1.3, 2.2, 2.4_

- [ ] 7. RAG e justificativa
  - [ ] 7.1 Reingerir base Chroma incluindo trechos sobre transporte de cargas (regime
        regular, Simples Nacional, split payment)
  - [ ] 7.2 Node `generate_justification` citando `fontes_citadas` a partir do RAG
  - [ ] 7.3 Teste garantindo que a alíquota do resultado nunca diverge da tool determinística,
        mesmo quando o texto do LLM menciona outro valor
  - _Requirements: 1.4, 1.6, 4.1, 4.2_

- [ ] 8. Memória de sessão
  - [ ] 8.1 Confirmar checkpointer SQLite mantém histórico por `thread_id` entre chamadas
  - [ ] 8.2 Endpoint para consultar simulações anteriores da mesma thread
  - _Requirements: 4.3, 4.4_

- [ ] 9. Human-in-the-loop e exportação
  - [ ] 9.1 Implementar `human_review` para o state do logitaxAgent
  - [ ] 9.2 `export_result` grava JSON e dispara webhook para o n8n somente após aprovação
  - _Requirements: 3.4, 5.5, 9.3_

- [ ] 10. Observabilidade
  - [ ] 10.1 Implementar `observability/logger.py` (logs JSON por node, chave `thread_id`)
  - [ ] 10.2 Implementar `observability/auditoria.py` (tabela SQLite de auditoria)
  - [ ] 10.3 Endpoint `GET /observabilidade/{thread_id}` cruzando os dois sinais
  - [ ] 10.4 Teste reconstruindo uma execução completa a partir dos logs + auditoria
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 11. Segurança e cenário adversarial (evidência formal)
  - [ ] 11.1 Documentar em `docs/evidencias/cenario-adversarial.md` o teste do item 3, com
        prints/logs do resultado
  - [ ] 11.2 Confirmar `.env.example`, `.gitignore` cobrindo segredos e `data/chroma_db/`
  - _Requirements: 5.3, 5.4_

- [ ] 12. QA com IA
  - [ ] 12.1 Rodar revisão de código por IA sobre um diff/PR real (o da paralelização, por
        exemplo) e salvar em `docs/qa/code-review-diff.md`
  - [ ] 12.2 Gerar/refinar testes de integração com apoio de IA cobrindo o fluxo completo
  - [ ] 12.3 Documentar priorização de teste em `docs/qa/priorizacao-testes.md`
        (Simples Nacional 2027 como cenário prioritário — justificar)
  - _Requirements: 7.1, 7.2, 7.3_

- [ ] 13. Pipeline CI e DevOps inteligente
  - [ ] 13.1 Criar/atualizar `.github/workflows/ci.yml` (lint → testes → build)
  - [ ] 13.2 Script `scripts/analisar_logs_ci.py` — IA explica logs de 2 etapas do pipeline
  - [ ] 13.3 Script `scripts/simular_falhas_tool.py` — gera falhas simuladas na tool externa
  - [ ] 13.4 Documentar detecção de anomalia e estimativa de risco em
        `docs/devops/deteccao-anomalia.md`
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 14. Integração low-code (n8n)
  - [ ] 14.1 Montar fluxo n8n: Webhook → Function (delta > 15%) → notificação
  - [ ] 14.2 Exportar fluxo como `low-code/n8n-fluxo-alerta.json`
  - [ ] 14.3 Documentar reprodução no README.md
  - _Requirements: 9.1, 9.2, 9.4_

- [ ] 15. Documentação de prompts e refinamento
  - [ ] 15.1 Atualizar `docs/prompts/` com os novos prompts (simulação, justificativa)
  - [ ] 15.2 Documentar um ciclo real de refinamento em
        `docs/evidencias/ciclo-refinamento.md`
  - _Requirements: 10.1, 10.2, 10.3_

- [ ] 16. README.md final e checklist de entrega
  - [ ] 16.1 Atualizar README com: descrição, classificação (sistema híbrido), diagrama,
        instruções de instalação/execução, cenários de uso, evidências, limitações, link do
        vídeo
  - [ ] 16.2 Conferir checklist final do documento do projeto avaliativo (Seção 7 do PDF)
  - _Requirements: todos_

- [ ] 17. Gravação do vídeo de demonstração
  - Seguir roteiro sugerido (10 min): problema/objetivo → arquitetura → 2 cenários (frete
    regular x prompt injection) → evidência de segurança → QA → pipeline/anomalia/risco →
    low-code → limitações
  - _Requirements: entrega final_
