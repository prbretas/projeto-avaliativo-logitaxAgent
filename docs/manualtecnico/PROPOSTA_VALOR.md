# Proposta de Valor — LogitaxAgent

## O Problema Real

A Reforma Tributária (LC 214/2025) muda completamente como empresas de transporte pagam impostos entre 2026 e 2033. O problema é:

1. **Ninguém sabe quanto vai pagar** — as alíquotas mudam a cada ano
2. **Cada rota tem impacto diferente** — SP→RJ ≠ SP→BA (ICMS varia)
3. **Cada regime tributário reage diferente** — Simples Nacional é prejudicado
4. **Contratos de frete precisam ser reajustados** — mas com base em quê?
5. **Contadores cobram caro** — para fazer simulação manual que demora dias

## Como o LogitaxAgent Resolve

| Sem LogitaxAgent | Com LogitaxAgent |
|-----------------|-----------------|
| Contador faz planilha manual (dias) | Simulação em segundos |
| 1 cenário por vez | 5 anos calculados em paralelo |
| Sem comparação de rotas | Compara qualquer rota automaticamente |
| Sem atualização quando lei muda | Script atualiza tabela automaticamente |
| Sem justificativa para diretoria | IA gera justificativa citando legislação |
| Sem alertas de impacto | Webhook alerta quando delta > 15% |

## Casos de Uso para Empresas

### 1. Transportadora renegociando contratos

**Cenário:** Transportadora tem 200 contratos de frete com vigência até 2030. Precisa saber quais contratos terão aumento de custo tributário para renegociar preço.

**Como usa:**
- Simula cada rota principal (SP→RJ, SP→MG, SP→BA, etc.)
- Compara regime atual vs novo para 2027, 2030, 2033
- Identifica rotas com aumento > 15%
- Gera relatório com justificativa legislativa para apresentar ao cliente

**Resultado:** Renegociação baseada em dados, não em achismo.

### 2. Embarcador planejando orçamento

**Cenário:** Empresa que contrata frete precisa prever quanto vai gastar de imposto nos próximos anos para planejar orçamento.

**Como usa:**
- Informa valor médio de frete, rota principal e regime
- Vê projeção ano a ano (2026→2033)
- IA explica por que o custo sobe ou desce
- Dashboard mostra tendência histórica

**Resultado:** Budget de frete com premissa tributária fundamentada.

### 3. Analista fiscal emitindo CT-e

**Cenário:** Analista precisa saber qual alíquota aplicar no CT-e para operação de hoje.

**Como usa:**
- Pergunta no chat: "Qual a alíquota de CBS para frete rodoviário em 2027?"
- Agente responde com valor exato e artigo da lei
- Pode perguntar follow-up: "E o ICMS residual?"

**Resultado:** Resposta imediata sem consultar manual da lei.

## O Que Torna Isso um "Agente" (vs uma Planilha)

| Recurso | Planilha Excel | LogitaxAgent |
|---------|---------------|-------------|
| Conversa natural | ❌ | ✅ "Quanto pago de SP pra BA?" |
| Lembra contexto | ❌ | ✅ "E se for Simples?" (lembra os dados) |
| Cita legislação | ❌ | ✅ Artigos da LC 214/2025 |
| Alerta automático | ❌ | ✅ Webhook quando delta > 15% |
| Atualiza dados | ❌ (manual) | ✅ Script verifica fonte oficial |
| Múltiplos regimes | Difícil | ✅ Troca com 1 clique |
| Segurança | ❌ | ✅ Não aceita manipulação de dados |
| Auditoria | ❌ | ✅ Log de toda decisão (quem, quando, o quê) |

## Valor Financeiro Estimado

Para uma transportadora com 100 contratos e frete médio de R$ 50.000/mês:

- **Sem simulação:** risco de não reajustar → perda de ~R$ 10.000/mês por contrato com aumento tributário
- **Com simulação manual:** 2h de contador por contrato × R$ 200/h = R$ 40.000
- **Com LogitaxAgent:** 100 simulações em minutos, custo = R$ 0 (Ollama local) ou ~R$ 1 (Groq)

## Fluxo de Aprovação (Human-in-the-loop)

O botão "Aprovar/Rejeitar" existe para o cenário empresarial:

```
Analista simula → Resultado aparece → Gerente aprova → Exporta relatório/webhook
```

**Quando faz sentido:**
- Empresa quer que resultado passe por validação antes de ir para o ERP
- Resultado com fallback (dados podem estar desatualizados) → revisor humano confirma
- Simulação usada como base para reajuste contratual (decisão financeira)

**Quando NÃO faz sentido:**
- Uso individual para consulta rápida (aprovação automática, que é o padrão)

## Limitações e Roadmap

| Limitação Atual | Solução Planejada |
|----------------|-------------------|
| Alíquotas de 2027+ são projeções | Atualização automática quando Senado publicar valores definitivos |
| ChromaDB precisa de reingestão quando lei muda | Script automatizado (GitHub Action semanal) |
| ICMS intraestadual genérico | Pode ser refinado por produto/segmento no futuro |
| Sem dashboard histórico | Próxima feature: histórico por rota/regime |
