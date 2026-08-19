# Comparativo: AgentClassTrib (M2.1) → LogitaxAgent (M2.2)

## Resumo Executivo

O **LogitaxAgent** é a evolução do **AgentClassTrib**, expandindo o escopo de "classificação tributária" para "simulação de impacto financeiro completo", com todas as bases do projeto anterior mantidas e significativamente aprimoradas.

---

## Visão Geral dos Dois Projetos

| Aspecto | AgentClassTrib (M2.1) | LogitaxAgent (M2.2) |
|---------|----------------------|---------------------|
| **Objetivo** | Classificar cClassTrib para CT-e | Simular impacto financeiro completo da transição IBS/CBS |
| **Saída** | Código cClassTrib + justificativa | Comparação regime atual vs novo (R$) + justificativa + recomendação |
| **Escopo temporal** | Classificação pontual (1 ano) | Simulação multi-ano (2026-2033) em paralelo |
| **LLM** | Ollama local apenas | Qualquer provider (Ollama/Groq/OpenAI) |
| **Interface** | CLI/JSON | API REST + Streamlit (formulário + chat conversacional) |
| **Avaliação** | M2.1 (30% do módulo) | M2.2 (60% do módulo) |

---

## O Que Foi Mantido (DNA do AgentClassTrib)

| Conceito do AgentClassTrib | Presente no LogitaxAgent | Localização |
|---------------------------|------------------------|-------------|
| LangGraph StateGraph | ✅ 12 nodes (vs ~8 planejados) | `src/graph/graph.py` |
| Estado tipado (Pydantic) | ✅ `AgentGraphState` + modelos Pydantic | `src/graph/state.py`, `src/models/` |
| RAG com ChromaDB | ✅ LC 214/2025 + NTs CT-e | `src/graph/nodes/retrieve_context.py` |
| Tabela determinística (não LLM) | ✅ `tabela_transicao_local.json` + CONFAZ | `data/` |
| Human-in-the-loop (interrupt) | ✅ `human_review` node com interrupt | `src/graph/nodes/human_review.py` |
| Export JSON (integração TMS) | ✅ Webhook n8n + JSON persistido | `src/graph/nodes/export_result.py` |
| Checkpointer SQLite | ✅ `SessionCheckpointer` (TTL 72h) | `src/persistence/checkpointer.py` |
| LLM gera justificativa, não calcula | ✅ Separação clara LLM vs determinístico | `src/graph/nodes/generate_justification.py` |
| Validação Pydantic de I/O | ✅ Em todos os endpoints e nodes | `src/models/` |
| Testes com golden set | ✅ 212 testes (unit + property + E2E) | `tests/` |
| Logs estruturados | ✅ JSON logs + SQLite auditoria | `src/observability/` |
| 100% local possível | ✅ Ollama + mode local (sem HTTP) | `.env` configurável |

---

## O Que o LogitaxAgent APRIMOROU

### 1. De classificação para simulação financeira

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| "O cClassTrib é X" | "Você vai pagar R$ 1.822 em 2030 (+12% vs hoje)" |
| Saída: código tributário | Saída: tabela comparativa com impacto em R$ |
| Útil para: preencher CT-e | Útil para: decisão financeira (reajuste de contrato) |

**Por que é melhor:** Classificar o cClassTrib resolve um problema operacional pontual. Simular o impacto financeiro resolve um problema estratégico (planejamento de reajuste de contratos de frete ao longo de 8 anos).

### 2. De single-year para multi-year paralelo

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| Classifica 1 operação por vez | Simula 5 anos em paralelo (fan-out/fan-in) |
| Sem comparação temporal | Mostra tendência 2026→2033 |

**Implementação:** `simular_anos` com `asyncio.gather` executa todos os anos simultaneamente.

### 3. De CLI para interface completa

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| Entrada/saída via JSON no terminal | Streamlit com formulário + chat + tabela |
| Sem interface visual | Cards, gráficos, tabela comparativa |
| Sem chat | Chat conversacional com memória |

### 4. De Ollama-only para multi-provider

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| "Não usar APIs pagas" (restrição) | Suporta Ollama, Groq, OpenAI, qualquer provider |
| Modelo fixo: llama3.1:8b | Configurável via `.env` |

### 5. De ICMS fixo para ICMS real por rota

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| Não calculava valores em R$ | Calcula com ICMS real por par de UFs (CONFAZ) |
| — | SP→RJ = 12%, SP→BA = 7%, diferença visível |

### 6. De testes manuais (golden set) para property-based testing

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| 15-20 cenários fixos | 212 testes: 177 unit + 25 property (Hypothesis) + 10 E2E |
| Teste manual de acerto | CI automatizado (GitHub Actions: lint → test → build) |

### 7. De webhook simulado para n8n real

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| "Simular integração com TMS" (export JSON) | Webhook real para n8n + alerta Slack |
| Sem automação low-code | Fluxo n8n importável com trigger |

### 8. De segurança básica para cenário adversarial completo

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| ".env no .gitignore" | Sanitização, detecção de injection, encapsulação [UNTRUSTED], audit trail |
| Sem cenário adversarial | Cenário documentado com evidência de que injection não funciona |

### 9. De documentação de projeto para documentação de negócio

| AgentClassTrib | LogitaxAgent |
|---------------|-------------|
| Documentação técnica (roadmap, issues) | Proposta de valor, manuais para leigos, casos de uso empresariais |
| Público: desenvolvedor | Público: analista fiscal, gestor logístico, avaliador |

---

## Funcionalidades do AgentClassTrib NÃO presentes no LogitaxAgent

| Funcionalidade | Status | Motivo |
|---------------|--------|--------|
| Determinação de cClassTrib (código específico) | Não implementado | Escopo mudou para simulação financeira (mais valor para decisão de negócio) |
| Golden set com taxa de acerto ≥80% | Substituído | Property-based testing com Hypothesis (milhares de combinações) é mais robusto |
| Embeddings locais (nomic-embed-text) | Mantido via ChromaDB | Funciona igual |

---

## Conclusão

O LogitaxAgent **mantém 100% da arquitetura conceitual** do AgentClassTrib (LangGraph, RAG, human-in-the-loop, tabela determinística, checkpointer) e **expande significativamente** em:

1. **Valor de negócio** — de classificação operacional para simulação estratégica
2. **Escala** — de 1 ano para multi-ano paralelo
3. **Interface** — de CLI para web + chat conversacional
4. **Qualidade** — de golden set manual para 212 testes automatizados com CI
5. **Integrabilidade** — de export JSON para API REST + webhook + n8n
6. **Segurança** — de .env para cenário adversarial completo com audit trail
7. **Flexibilidade** — de Ollama-only para qualquer LLM provider

É uma evolução natural que aproveita os fundamentos do M2.1 e constrói um sistema substancialmente mais completo para o M2.2.
