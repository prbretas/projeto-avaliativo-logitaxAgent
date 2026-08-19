# Manual de Configuração da IA — LogitaxAgent
## Como Configurar o Modelo de Linguagem (LLM)

---

## O que é o LLM?

O LLM (Large Language Model) é a "inteligência artificial" que permite ao sistema:
- Gerar justificativas legislativas em linguagem natural
- Entender suas perguntas no chat (ex: "Quanto vou pagar de frete de SP pra RJ?")
- Criar análises personalizadas dos resultados

**Sem o LLM configurado**, o sistema ainda funciona! Os cálculos de impostos são 100% determinísticos. Você só perde a justificativa em texto e o chat inteligente.

---

## Qual LLM eu devo usar?

Você pode usar **qualquer um** dos seguintes. Escolha o que preferir:

| Opção | Custo | Velocidade | Qualidade | Ideal para |
|-------|-------|-----------|-----------|------------|
| **Ollama (local)** | Grátis | Média | Boa | Quem tem PC com 8GB+ RAM |
| **Groq** | Grátis (com limite) | Muito rápida | Boa | Quem quer velocidade sem pagar |
| **OpenAI** | Pago (~R$0,01/consulta) | Rápida | Excelente | Quem quer máxima qualidade |

---

## Opção 1: Ollama (Grátis, roda no seu PC)

### Passo 1: Instalar o Ollama

1. Acesse: https://ollama.com/download
2. Baixe o instalador para Windows
3. Execute o instalador e aguarde finalizar

### Passo 2: Baixar o modelo de IA

1. Abra o **Prompt de Comando** (tecla Windows → cmd → Enter)
2. Execute:
   ```
   ollama pull llama3.1
   ```
3. Aguarde o download (pode demorar 5-10 minutos, são ~4GB)

### Passo 3: Verificar que está funcionando

1. No Prompt de Comando, execute:
   ```
   ollama list
   ```
2. Deve aparecer `llama3.1` na lista

### Passo 4: Configurar o LogitaxAgent

1. Abra o arquivo `.env` na pasta do projeto (com o Bloco de Notas)
2. Edite as linhas de LLM para ficarem assim:
   ```
   LLM_MODEL_NAME=llama3.1
   LLM_ENDPOINT=http://localhost:11434/v1
   OPENAI_API_KEY=ollama
   ```
3. Salve o arquivo

### Passo 5: Usar o sistema

Sempre que for usar o LogitaxAgent com IA, certifique-se que o Ollama está rodando:
- Ele inicia automaticamente com o Windows (ícone na bandeja do sistema)
- Se não estiver rodando, abra o aplicativo "Ollama" no menu Iniciar

> **Modelos alternativos para Ollama:**
> - `llama3.1` — equilibrado (recomendado)
> - `llama3.1:70b` — melhor qualidade (precisa 32GB+ RAM)
> - `mistral` — mais leve (funciona em PCs com 4GB RAM)
> - `gemma2` — bom para português

---

## Opção 2: Groq (Grátis na nuvem, muito rápido)

### Passo 1: Criar conta no Groq

1. Acesse: https://console.groq.com
2. Crie uma conta (pode usar Google ou email)
3. Vá em **API Keys** no menu lateral
4. Clique em **Create API Key**
5. Copie a chave gerada (começa com `gsk_...`)

### Passo 2: Configurar o LogitaxAgent

1. Abra o arquivo `.env` na pasta do projeto
2. Edite as linhas de LLM:
   ```
   LLM_MODEL_NAME=llama-3.1-70b-versatile
   LLM_ENDPOINT=https://api.groq.com/openai/v1
   OPENAI_API_KEY=gsk_sua_chave_aqui
   ```
3. Salve o arquivo

> **Limite gratuito do Groq:** ~30 requests por minuto. Suficiente para uso normal.

---

## Opção 3: OpenAI (Pago, máxima qualidade)

### Passo 1: Criar conta na OpenAI

1. Acesse: https://platform.openai.com
2. Crie uma conta e adicione créditos (~US$5 é suficiente para meses de uso)
3. Vá em **API Keys**
4. Clique em **Create new secret key**
5. Copie a chave (começa com `sk-...`)

### Passo 2: Configurar o LogitaxAgent

1. Abra o arquivo `.env` na pasta do projeto
2. Edite as linhas de LLM:
   ```
   LLM_MODEL_NAME=gpt-4o-mini
   LLM_ENDPOINT=https://api.openai.com/v1
   OPENAI_API_KEY=sk-sua_chave_aqui
   ```
3. Salve o arquivo

---

## Como editar o arquivo .env

1. Navegue até a pasta do projeto no Windows Explorer
2. Encontre o arquivo `.env` (se não aparecer, ative "Mostrar arquivos ocultos")
3. Clique com botão direito → **Abrir com** → **Bloco de Notas**
4. Edite as 3 linhas de LLM conforme a opção escolhida
5. Salve (Ctrl+S) e feche

Se o arquivo `.env` não existir:
1. Encontre o arquivo `.env.example`
2. Copie e renomeie para `.env`
3. Edite conforme instruções acima

---

## Como verificar se está funcionando

1. Abra o sistema: `streamlit run app_ui.py`
2. Vá na aba **"💬 Chat com o Agente"**
3. Digite: "Olá"
4. Se o agente responder de forma inteligente → LLM configurado corretamente!
5. Se responder com texto genérico → verifique a configuração

---

## Problemas Comuns

### "O chat não entende minhas perguntas"
- Verifique se o Ollama está rodando (ícone na bandeja)
- Verifique se o modelo foi baixado (`ollama list`)
- Confira as 3 linhas no `.env`

### "Erro de conexão / timeout"
- **Ollama**: Certifique-se que está rodando. Tente `ollama serve` no terminal.
- **Groq/OpenAI**: Verifique sua conexão com a internet e se a API key está correta

### "O sistema funciona mas sem justificativa"
- O cálculo sempre funciona (não depende de IA)
- A justificativa legislativa só aparece se o LLM estiver configurado
- O comentário analítico (🤖) funciona MESMO sem LLM (é determinístico)

### "Quero trocar de provedor"
- Basta editar as 3 linhas no `.env` e reiniciar o Streamlit (Ctrl+C e rodar novamente)

---

## Resumo Rápido

| Provedor | LLM_MODEL_NAME | LLM_ENDPOINT | OPENAI_API_KEY |
|----------|---------------|-------------|----------------|
| Ollama | llama3.1 | http://localhost:11434/v1 | ollama |
| Groq | llama-3.1-70b-versatile | https://api.groq.com/openai/v1 | gsk_... |
| OpenAI | gpt-4o-mini | https://api.openai.com/v1 | sk-... |
