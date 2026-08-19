# Manual de Testes — LogitaxAgent
## Como Executar os Testes (Para Leigos)

---

## O que são os testes?

Os testes são verificações automáticas que confirmam que o sistema funciona corretamente. É como um "checklist automático" que roda em segundos e avisa se algo está quebrado.

O LogitaxAgent possui **212 testes** divididos em:
- **177 testes unitários** — testam cada pedaço do sistema isoladamente
- **25 testes de propriedade** — testam regras matemáticas com milhares de combinações
- **10 testes de integração** — testam o sistema inteiro de ponta a ponta

---

## Pré-requisitos

Antes de rodar os testes, você precisa ter o projeto instalado. Se ainda não fez isso, siga o "Passo 0" do `MANUAL_USUARIO.md`.

**Resumo rápido se já instalou:**
- Python instalado ✅
- Projeto baixado ✅
- `pip install -e ".[dev]"` executado ✅

---

## PASSO A PASSO

### Passo 1: Abrir o Prompt de Comando

1. Pressione a tecla **Windows** no teclado
2. Digite **cmd**
3. Pressione **Enter**
4. Uma janela preta vai abrir

---

### Passo 2: Navegar até a pasta do projeto

Digite o comando abaixo e pressione Enter:

```
cd C:\LogitaxAgent\projeto-avaliativo-logitaxAgent-main
```

> ⚠️ Se você extraiu o projeto em outra pasta, ajuste o caminho.  
> Dica: se não lembra onde está, procure a pasta que contém o arquivo `pyproject.toml`.

---

### Passo 3: Rodar TODOS os testes de uma vez

Digite e pressione Enter:

```
pytest tests/ -v
```

**O que vai acontecer:**
- O sistema executa todos os 211 testes
- Demora entre 30 segundos e 2 minutos
- Cada teste aparece com ✅ PASSED (passou) ou ❌ FAILED (falhou)
- No final aparece um resumo: `211 passed` = tudo funcionando

**Exemplo do que você vai ver:**
```
tests/test_calculo.py::test_tributo_atual_10000 PASSED
tests/test_calculo.py::test_tributo_novo_2026 PASSED
tests/test_sanitize_input.py::test_injection_blocked PASSED
...
========================= 212 passed in 45.32s =========================
```

---

### Passo 4 (Opcional): Rodar apenas um tipo de teste

Se quiser rodar apenas um grupo específico:

#### Apenas testes unitários (mais rápidos, ~15s):
```
pytest tests/test_calculo.py tests/test_parse_operacao.py tests/test_sanitize_input.py tests/test_tool_transicao.py tests/test_client_transicao.py tests/test_checkpointer.py tests/test_reclassificacao.py tests/test_nodes_simulacao.py tests/test_ingestao.py tests/test_retrieve_context.py -v
```

#### Apenas testes de propriedade (Hypothesis, ~60s):
```
pytest tests/test_properties_*.py -v
```

#### Apenas testes de integração (end-to-end, ~10s):
```
pytest tests/test_simulacao_integracao.py -v
```

#### Apenas testes de segurança (prompt injection):
```
pytest tests/test_properties_seguranca.py tests/test_sanitize_input.py -v
```

#### Apenas testes da Tool_Transicao:
```
pytest tests/test_properties_tool.py tests/test_tool_transicao.py tests/test_client_transicao.py -v
```

---

### Passo 5: Entender os resultados

| O que aparece | O que significa |
|---------------|----------------|
| `PASSED` (verde) | O teste passou — funcionalidade está correta ✅ |
| `FAILED` (vermelho) | O teste falhou — algo pode estar quebrado ❌ |
| `SKIPPED` (amarelo) | O teste foi pulado (geralmente precisa de algo extra, como ChromaDB populado) ⚠️ |
| `ERROR` (vermelho) | Erro de configuração, não do código em si |

**Se todos passaram:** `212 passed` → sistema 100% funcional!

**Se algum falhou:** Anote o nome do teste que falhou e o erro mostrado. Exemplo:
```
FAILED tests/test_calculo.py::test_tributo_atual_10000
    AssertionError: expected 2125.00, got 2124.99
```

---

## Rodar com relatório visual (HTML)

Se quiser gerar um relatório bonito em HTML:

```
pip install pytest-html
pytest tests/ -v --html=relatorio_testes.html --self-contained-html
```

Depois abra o arquivo `relatorio_testes.html` no navegador (dê dois cliques nele).

---

## Rodar com cobertura de código

Para ver quanto do código está coberto por testes:

```
pip install pytest-cov
pytest tests/ --cov=src --cov-report=html
```

Depois abra a pasta `htmlcov/index.html` no navegador.

---

## O que cada arquivo de teste verifica

| Arquivo | O que testa |
|---------|-------------|
| `test_calculo.py` | Cálculos de imposto (PIS, COFINS, ICMS, IBS, CBS, Delta) |
| `test_parse_operacao.py` | Validação dos dados de entrada (rejeita campos inválidos) |
| `test_sanitize_input.py` | Proteção contra ataques (prompt injection) |
| `test_tool_transicao.py` | Endpoint de consulta de alíquotas |
| `test_client_transicao.py` | Retry e fallback quando tool está indisponível |
| `test_checkpointer.py` | Memória de sessão (salvar/recuperar simulações) |
| `test_reclassificacao.py` | Limite de tentativas (máximo 3) |
| `test_nodes_simulacao.py` | Nodes do grafo (route, regime, simulação) |
| `test_ingestao.py` | Indexação de legislação no ChromaDB (RAG) |
| `test_retrieve_context.py` | Busca de trechos legislativos |
| `test_simulacao_integracao.py` | Fluxo completo de ponta a ponta |
| `test_properties_calculo.py` | Propriedades matemáticas dos cálculos tributários |
| `test_properties_fanout.py` | Paralelização correta da simulação multi-ano |
| `test_properties_human_review.py` | Regras de aprovação/rejeição humana |
| `test_properties_observabilidade.py` | Logs e auditoria estruturados |
| `test_properties_seguranca.py` | Resistência a prompt injection |
| `test_properties_sessao.py` | Persistência e recuperação de sessão |
| `test_properties_stopping.py` | Condição de parada (max reclassificações) |
| `test_properties_tool.py` | Resiliência da Tool_Transicao (retry/fallback) |
| `test_properties_validation.py` | Validação de entrada com combinações diversas |
| `test_properties_webhook.py` | Envio de webhook n8n |

---

## Resumo Rápido (Cola)

```
1. Abra o cmd (tecla Windows → cmd → Enter)
2. cd C:\LogitaxAgent\projeto-avaliativo-logitaxAgent-main
3. pytest tests/ -v
4. Espere ~1 minuto
5. Resultado: "212 passed" = tudo OK ✅
```

---

## Problemas Comuns

### "pytest não é reconhecido como comando"
Execute primeiro:
```
pip install -e ".[dev]"
```

### "ModuleNotFoundError: No module named 'src'"
Você precisa estar na pasta raiz do projeto (a que contém `pyproject.toml`). Verifique com:
```
dir pyproject.toml
```
Se aparecer "Arquivo não encontrado", você está na pasta errada.

### "Alguns testes deram SKIPPED"
Normal — são testes que precisam do ChromaDB populado. Para popular:
```
python scripts/run_ingestao.py
```
Depois rode os testes novamente.

### "Testes demorando mais de 3 minutos"
Os testes de propriedade (Hypothesis) geram muitas combinações. Se quiser mais rápido:
```
pytest tests/ -v --hypothesis-seed=0 -x
```
O `-x` para no primeiro erro (mais rápido para diagnóstico).
