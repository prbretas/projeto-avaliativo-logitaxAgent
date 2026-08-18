# Code Review por IA — Evidência

## PR #38: feat: implementação base do simulador IBS/CBS

### Issues identificadas pelo code review automatizado

#### 1. Bug: Arredondamento inconsistente no cálculo tributário

**Arquivo:** `src/graph/nodes/calculo.py`  
**Severidade:** Bug  
**Descrição:** A função `calcular_tributo_novo` realizava arredondamento intermediário em cada componente (CBS, IBS, ICMS) antes de somá-los, o que podia resultar em discrepância de ±0.01 no valor final.  
**Sugestão:** Somar todos os componentes primeiro e arredondar apenas o resultado final para 2 casas decimais.  
**Status:** Corrigido.

#### 2. Style: Imports não ordenados em models/__init__.py

**Arquivo:** `src/models/__init__.py`  
**Severidade:** Style  
**Descrição:** Os imports dos modelos não seguiam a ordem alfabética conforme convenção do projeto.  
**Sugestão:** Usar `ruff check --fix` para auto-organizar imports com isort.  
**Status:** Corrigido via ruff.

#### 3. Performance: Carregamento da tabela JSON em cada request

**Arquivo:** `src/tools/tabela_transicao.py`  
**Severidade:** Performance  
**Descrição:** `_carregar_tabela_transicao()` abre e lê o arquivo JSON a cada consulta ao endpoint, sem cache.  
**Sugestão:** Carregar o JSON uma vez no startup do módulo (module-level) e reutilizar em memória, já que os dados são estáticos.  
**Status:** Identificado para futuro refinamento. Impacto mínimo com volume atual.

#### 4. Security: Campo observacoes sem limite de tamanho no model

**Arquivo:** `src/models/operacao.py`  
**Severidade:** Security  
**Descrição:** O campo `observacoes` aceita strings de qualquer tamanho no Pydantic model, embora o node `sanitize_input` trunca para 500 chars depois.  
**Sugestão:** Adicionar `max_length=500` diretamente no validador Pydantic para defense-in-depth.  
**Status:** Implementado — validação dupla (model + sanitize node).

---

## Ferramenta utilizada

- Review assistido por IA (Kiro) durante desenvolvimento
- Análise estática: ruff check + ruff format
- Validação manual dos pontos identificados
