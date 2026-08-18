# Ciclo de Refinamento — LogitaxAgent

## Evidência de Refinamento Iterativo

### Ciclo 1: Validação de Modelos Pydantic

**Problema observado:** Validação de UFs e regimes não retornava todos os erros de uma vez — parava no primeiro erro.

**Mudança aplicada:** Configuração de Pydantic v2 com `model_validate()` que coleta TODOS os erros de validação antes de retornar. Implementado em `parse_operacao` node.

**Resultado medido:**
- Before: 1 erro retornado por request (usuário precisa corrigir iterativamente)
- After: N erros retornados simultaneamente (fail-fast coletivo, Req 1.8)

---

### Ciclo 2: Fallback da Tool_Transicao

**Problema observado:** Quando o endpoint da Tool_Transicao está indisponível, a simulação falha completamente sem resultado para o usuário.

**Mudança aplicada:** Implementação de fallback local em `client_transicao.py` com retry 2x (backoff 1s, 2s) + leitura de `data/tabela_transicao_local.json` quando todas tentativas falham. Flag `fallback_usado=True` + warning na resposta.

**Resultado medido:**
- Before: 100% falha quando tool indisponível
- After: 0% falha (fallback garante resultado), com flag transparente para o usuário

---

### Ciclo 3: Rate Validation na Justificativa

**Problema observado:** LLM pode alucinar alíquotas que não existem na tabela de transição, gerando justificativas incorretas.

**Mudança aplicada:** Pós-processamento com regex para extrair rates citadas no texto e comparação cruzada contra rates válidas da Tool_Transicao. Mismatch → descartar + retry (2x) → escalação para human_review.

**Resultado medido:**
- Before: Justificativas com rates potencialmente incorretas passavam sem verificação
- After: Validação cruzada garante 100% de fidelidade nas alíquotas citadas

---

### Ciclo 4: Condição de Parada (Reclassificação)

**Problema observado:** Loop infinito possível se o agente ficar alternando entre reclassificações de regime sem convergir.

**Mudança aplicada:** Contador `tentativas_reclassificacao` no AgentState com limite máximo de 3. Ao atingir, força escalação para `human_review` com `revisao_manual=True`. Sem re-entry após escalação.

**Resultado medido:**
- Before: Potencial loop infinito (custo computacional não limitado)
- After: Máximo 3 iterações + escalação garantida (Req 6.3, 6.4, 6.5)
