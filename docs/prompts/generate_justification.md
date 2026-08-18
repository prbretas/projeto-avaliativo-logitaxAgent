# Prompt: generate_justification

## Descrição

Prompt utilizado pelo node `generate_justification` para gerar justificativa técnica em linguagem natural sobre o impacto da transição IBS/CBS no frete, citando legislação recuperada via RAG.

**Node:** `src/graph/nodes/generate_justification.py`  
**Requirements:** 7.2, 7.4, 7.5

---

## System Prompt

```
Você é um analista tributário especialista em Reforma Tributária brasileira.
Responda APENAS com a justificativa técnica solicitada, sem preâmbulos ou explicações adicionais.
```

---

## User Prompt (Template)

```
Você é um analista tributário especializado na Reforma Tributária brasileira (LC 214/2025).

## REGRAS OBRIGATÓRIAS

1. Gere uma justificativa técnica em português brasileiro sobre o impacto da transição IBS/CBS no frete.
2. Cite APENAS as alíquotas exatas que constam nos resultados de cálculo fornecidos abaixo.
3. Para cada ano simulado, mencione as alíquotas CBS e IBS aplicadas (conforme Tabela de Transição).
4. Cite artigos da legislação SOMENTE se estiverem nos trechos RAG fornecidos.
5. NÃO invente artigos, números de lei ou alíquotas que não estejam nos dados fornecidos.
6. A justificativa deve ser clara, concisa e auditável.
7. Formato de saída: texto corrido com parágrafos, citando fontes entre parênteses.

## CONTEXTO DA OPERAÇÃO

- Modal: {modal}
- Origem UF: {origem_uf}
- Destino UF: {destino_uf}
- Regime Tributário: {regime}
- Valor do Frete: R$ {valor_frete:,.2f}

## TRECHOS LEGISLATIVOS (RAG)

{trechos_formatados}

## RESULTADOS DE CÁLCULO POR ANO

{resultados_formatados}

## INSTRUÇÃO FINAL

Com base nos trechos legislativos e resultados acima, elabore a justificativa técnica
explicando o impacto da transição tributária IBS/CBS sobre esta operação de frete.
Mencione as alíquotas exatas de cada ano simulado e cite os artigos relevantes da
legislação quando disponíveis nos trechos RAG.
```

---

## Regras de Comportamento (Behavior Rules)

| # | Regra | Justificativa |
|---|-------|---------------|
| 1 | Citar APENAS alíquotas presentes nos resultados de cálculo | Evitar alucinação de rates (Req 7.4) |
| 2 | Citar artigos SOMENTE se nos trechos RAG | Evitar citações falsas de legislação (Req 7.2) |
| 3 | NÃO inventar dados fora do contexto fornecido | Manter auditabilidade |
| 4 | Formato texto corrido com citações entre parênteses | Facilitar leitura por analista fiscal |
| 5 | Temperatura baixa (0.3) | Reduzir variabilidade e alucinação |
| 6 | Max tokens: 1500 | Limitar verbosidade |

---

## Formato de Saída Esperado

Texto corrido em português brasileiro, com:
- Parágrafos explicando o impacto por ano
- Alíquotas citadas com valores exatos (ex: "CBS 0,9% + IBS 0,1%")
- Artigos legislativos entre parênteses (ex: "(art. 343, LC 214/2025)")
- Conclusão com o impacto consolidado (delta percentual)

**Exemplo de saída:**

> A operação de frete rodoviário entre SP e RJ sob regime de Lucro Real apresenta impacto
> progressivo com a transição tributária. No ano de 2026, em fase de teste, aplica-se a alíquota
> combinada de 1,0% (CBS 0,9% + IBS 0,1%), conforme art. 343 da LC 214/2025, mantendo-se
> o ICMS integral de 12,0%. Para 2033, com a extinção completa do ICMS e aplicação plena
> do IBS + CBS, a carga tributária nova será de 8,8%, representando uma redução de -58,59%
> em relação ao regime atual (PIS 1,65% + COFINS 7,6% + ICMS 12,0% = 21,25%).

---

## Variáveis de Entrada (Input Variables)

| Variável | Tipo | Origem | Descrição |
|----------|------|--------|-----------|
| `modal` | str | `OperacaoFrete.modal` | Modal de transporte |
| `origem_uf` | str | `OperacaoFrete.origem_uf` | UF de origem |
| `destino_uf` | str | `OperacaoFrete.destino_uf` | UF de destino |
| `regime` | str | `OperacaoFrete.regime_tributario` | Regime tributário |
| `valor_frete` | float | `OperacaoFrete.valor_frete` | Valor do frete em R$ |
| `trechos_formatados` | str | `retrieve_context` node | Trechos RAG formatados com citação |
| `resultados_formatados` | str (JSON) | `agregar_resultados` node | Resultados de cálculo por ano |

---

## Validação Pós-Geração (Rate Matching)

Após a geração pelo LLM, o node executa validação de integridade:

1. **Extração de rates:** Regex `(\d+(?:[.,]\d+)?)\s*%` busca todos percentuais no texto
2. **Validação cruzada:** Cada percentual é comparado contra rates válidas:
   - Rates da Tool_Transicao para os anos simulados (CBS, IBS, ICMS phase-out, combinada)
   - Constantes do Regime_Atual (PIS 1,65%, COFINS 7,6%, ICMS 12,0%, total 21,25%)
   - Delta percentuais dos resultados de cálculo
   - Percentuais comuns (0%, 60%, 70%, 80%, 90%, 100%)
3. **Tolerância:** 0,01 pontos percentuais para arredondamento
4. **Em caso de mismatch:**
   - Descarta a justificativa gerada
   - Loga evento de integridade na auditoria (`event: "integridade"`)
   - Retry até 2x adicionais (total 3 tentativas)
   - Se todas falham: escala para `human_review` com `revisao_manual=True`

---

## Configuração (Environment Variables)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `LLM_MODEL_NAME` | `gpt-4o-mini` | Nome do modelo LLM |
| `LLM_ENDPOINT` | `https://api.openai.com/v1` | Endpoint da API LLM |
| `OPENAI_API_KEY` | (obrigatório) | API key para autenticação |

---

## Parâmetros LLM

| Parâmetro | Valor | Justificativa |
|-----------|-------|---------------|
| `temperature` | 0.3 | Baixa para minimizar alucinação |
| `max_tokens` | 1500 | Suficiente para justificativa técnica completa |
| `timeout` | 30s | Tempo máximo para resposta da API |
| `max_retries` | 2 | Retries em caso de rate mismatch |
