# Priorização de Testes — LogitaxAgent

## Ranking de Cenários por Risco

Priorização baseada em: **impacto financeiro** × **complexidade de cálculo**.

| # | Cenário | Impacto Financeiro | Complexidade | Score | Prioridade |
|---|---------|-------------------|--------------|-------|-----------|
| 1 | Cálculo de alíquotas no phase-out ICMS (2029-2032) | **Alto** — valores intermediários com proporções variáveis | **Alta** — múltiplas alíquotas combinadas com percentual de fase | 9/10 | **Crítica** |
| 2 | Delta percentual com regime Simples Nacional (credit=0) | **Alto** — Simples representa maioria das empresas de transporte | **Média** — lógica simplificada mas com edge case de divisão por zero | 8/10 | **Crítica** |
| 3 | Fallback da Tool_Transicao com dados desatualizados | **Alto** — versão local pode ter alíquotas defasadas | **Média** — comparação de versões, flag de warning | 7/10 | **Alta** |
| 4 | Validação cruzada de rates na justificativa (LLM hallucination) | **Médio** — justificativa incorreta pode levar a decisões erradas | **Alta** — regex extraction + fuzzy matching de percentuais | 7/10 | **Alta** |
| 5 | Fan-out com falha parcial em subset de anos | **Médio** — resultado incompleto pode subestimar impacto | **Média** — lógica de agregação parcial | 6/10 | **Média** |

## Justificativa

### Cenário 1: Phase-out ICMS
O phase-out de ICMS (90%/80%/70%/60% da base) é o cálculo mais complexo porque combina alíquotas novas (CBS+IBS) com percentual decrescente de ICMS. Um erro aqui afeta diretamente o delta percentual reportado ao usuário, que é a métrica principal de decisão.

### Cenário 2: Simples Nacional
Empresas optantes pelo Simples não têm direito a créditos (credit_factor=0), o que significa carga tributária nova mais alta. Como a maioria das transportadoras brasileiras é de pequeno porte (Simples), erros neste cenário afetam o maior volume de simulações.

### Cenário 3: Fallback com dados desatualizados
Se a tabela local JSON não acompanhar atualizações legislativas, o fallback pode retornar alíquotas incorretas. O sistema deve alertar claramente sobre o uso de fallback e a versão dos dados.

### Cenário 4: Alucinação de rates pelo LLM
O LLM pode citar alíquotas que não existem na tabela de transição. A validação pós-geração é a última linha de defesa antes de apresentar a justificativa ao revisor humano.

### Cenário 5: Falha parcial no fan-out
Se a simulação de um ano falha (ex: 2030) mas outros sucessem, o resultado parcial pode dar impressão errada do impacto ao longo do tempo. O sistema deve indicar claramente quais anos falharam.

## Recomendação

- **Testes prioritários:** Property tests para cenários 1 e 2 (verificação matemática)
- **Testes de integração:** Cenários 3 e 5 (fallback e falha parcial)
- **Testes de validação:** Cenário 4 (rate matching)
