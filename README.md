# LogitaxAgent — Simulador de Impacto IBS/CBS

Sistema agêntico (LangGraph) para simulação do impacto financeiro da Reforma Tributária brasileira (IBS/CBS) sobre operações de frete.

## Pré-requisitos

- Python 3.12+
- pip (gerenciador de pacotes)
- n8n (para fluxo de alertas, opcional)

## Instalação

```bash
# Clonar o repositório
git clone https://github.com/prbretas/projeto-avaliativo-logitaxAgent.git
cd projeto-avaliativo-logitaxAgent

# Instalar dependências
pip install -e ".[dev]"

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas configurações
```

## Uso

### Executar a API

```bash
uvicorn src.api.main:app --reload --port 8000
```

### Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/simular` | Submete operação de frete |
| GET | `/tools/tabela-transicao` | Consulta alíquotas |
| POST | `/review/{thread_id}` | Aprova/rejeita resultado |
| GET | `/observabilidade/{thread_id}` | Timeline de execução |
| GET | `/health` | Health check |

### Executar testes

```bash
pytest tests/ -v
```

### Executar lint

```bash
ruff check src/ tests/
```

## Fluxo n8n — Alertas de Impacto

### Pré-requisitos

1. n8n instalado e rodando (self-hosted ou cloud)
2. Credenciais Slack configuradas (ou outro canal de notificação)

### Import step-by-step

1. Abra o n8n → **Workflows** → **Import from File**
2. Selecione `low-code/n8n-fluxo-alerta.json`
3. Configure a variável de ambiente `DELTA_THRESHOLD_PCT` (default: 15%)
4. Configure as credenciais do Slack no nó "Send Alert"
5. Ative o workflow
6. Copie a URL do webhook e configure em `.env` como `WEBHOOK_N8N_URL`

### Payload de exemplo

```json
{
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "delta_percentual": -58.59,
  "resultados_por_ano": [
    {"ano": 2026, "valor_tributo_atual": 2125.0, "valor_tributo_novo": 100.0, "delta_percentual": -95.29},
    {"ano": 2033, "valor_tributo_atual": 2125.0, "valor_tributo_novo": 880.0, "delta_percentual": -58.59}
  ],
  "timestamp": "2026-01-15T10:30:00Z"
}
```

### Output esperado

- Se `|delta_percentual|` >= threshold (15%): envia alerta Slack + responde `{"status": "alert_sent"}`
- Se `|delta_percentual|` < threshold: responde `{"status": "below_threshold"}`

### Configuração do Threshold

- **Default:** 15%
- **Range:** 1-100%
- **Variável:** `DELTA_THRESHOLD_PCT` (environment variable no n8n)

## Estrutura do Projeto

```
src/
├── api/          # Endpoints FastAPI
├── graph/        # LangGraph StateGraph
│   └── nodes/    # Nodes do grafo
├── models/       # Modelos Pydantic
├── observability/# Logs e auditoria
├── persistence/  # SQLite checkpointer
└── tools/        # Tool_Transicao (endpoint + client)
tests/            # Testes unitários e integração
scripts/          # Scripts DevOps
data/             # Dados locais (tabela transição)
docs/             # Documentação
low-code/         # Fluxos n8n
```

## Licença

Projeto acadêmico — M2S12 IA para Desenvolvedores.
