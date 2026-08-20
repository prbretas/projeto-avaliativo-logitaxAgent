# Manual de Instruções — LogitaxAgent

---

## O que é o LogitaxAgent?

O LogitaxAgent calcula quanto sua empresa de frete vai pagar de imposto **antes e depois** da Reforma Tributária (IBS/CBS). Ele compara o regime atual com o novo regime que será implementado entre 2026 e 2033.

Você informa os dados de um frete → o sistema mostra se vai pagar mais ou menos imposto.

---

## O Sistema Tem Interface Gráfica?
## O Sistema Tem Interface Gráfica?

**SIM!** O sistema possui uma **interface unificada** com duas abas:

1. **📊 Simulador** — Preencha os campos e clique em simular (formulário visual)
2. **💬 Chat com o Agente** — Converse em linguagem natural, como um assistente

Tudo em uma única tela: `streamlit run app_ui.py`

Também existe a interface da API (Swagger) para usuários mais técnicos.
---

## PASSO A PASSO COMPLETO

### Passo 0: Pré-requisitos (Só na primeira vez)

Antes de tudo, você precisa ter instalado no seu computador:

#### A) Instalar o Python

1. Abra o navegador e vá em: https://www.python.org/downloads/
2. Clique no botão amarelo **"Download Python"** (versão 3.11 ou superior)
3. Execute o instalador
4. **IMPORTANTE**: Na primeira tela do instalador, marque a caixa ✅ **"Add Python to PATH"**
5. Clique em "Install Now"
6. Aguarde finalizar e feche

#### B) Baixar o projeto

1. Abra o navegador e vá em: https://github.com/prbretas/projeto-avaliativo-logitaxAgent
2. Clique no botão verde **"Code"**
3. Clique em **"Download ZIP"**
4. Extraia o ZIP numa pasta fácil de encontrar (ex: `C:\LogitaxAgent\`)

#### C) Instalar as dependências

1. Abra o **Prompt de Comando** (pressione a tecla Windows, digite `cmd` e pressione Enter)
2. Navegue até a pasta do projeto digitando:
   ```
   cd C:\LogitaxAgent\projeto-avaliativo-logitaxAgent-main
   ```
3. Execute o comando de instalação:
   ```
   pip install -e ".[dev]"
   ```
4. Aguarde finalizar (pode demorar 2-3 minutos)
5. Copie o arquivo de configuração de exemplo:
   ```
   copy .env.example .env
   ```
   > 💡 O arquivo `.env` contém configurações opcionais (como chave da OpenAI para justificativas com IA). A simulação básica funciona sem editar nada.

**Pronto! Você só precisa fazer isso UMA VEZ.**

---

### Passo 1: Abrir o Sistema (Toda vez que quiser usar)

1. Abra o **Prompt de Comando** (tecla Windows → digite `cmd` → Enter)
2. Navegue até a pasta do projeto:
   ```
   cd C:\LogitaxAgent\projeto-avaliativo-logitaxAgent-main
   ```
3. Execute o comando para abrir a interface:
   ```
   streamlit run app_ui.py
   ```
   A interface abre com **duas abas**: Simulador (formulário) e Chat (conversacional).
4. **O navegador vai abrir automaticamente** com a interface do LogitaxAgent
5. Se não abrir sozinho, acesse: http://localhost:8501

> ⚠️ **Não feche a janela preta do Prompt de Comando enquanto estiver usando o sistema!** É ela que mantém o sistema rodando.

---

### Passo 2: Preencher os Dados do Frete

Na interface que abriu no navegador:

1. **Tipo de Transporte**: Selecione o modal (Rodoviário, Aéreo, etc.)
2. **Estado de Origem**: Selecione a UF de onde sai a carga
3. **Estado de Destino**: Selecione a UF para onde vai a carga
4. **Regime Tributário**: Selecione o regime da empresa
   - Não sabe qual é? **Pergunte ao contador da empresa**
   - Se for MEI ou empresa pequena → provavelmente é **Simples Nacional**
5. **Valor do Frete (R$)**: Digite o valor do frete
6. **Ano de Referência**: Escolha o ano que quer simular (2026 a 2033)

---

### Passo 3: Clicar em "Simular"

1. Clique no botão roxo **"🚀 Simular Impacto Tributário"**
2. Aguarde alguns segundos
3. O resultado aparece logo abaixo

---

### Passo 4: Ler os Resultados

O sistema mostra cards com os resultados para cada ano:

| O que aparece | O que significa |
|---------------|----------------|
| **Valor em R$** | Quanto vai pagar de imposto no regime novo |
| **Seta verde ↓ com %** | Vai pagar **MENOS** (economia!) |
| **Seta vermelha ↑ com %** | Vai pagar **MAIS** (cuidado!) |
| **"Atual: R$ X"** | Quanto paga hoje |
| **⚠️ Dados de fallback** | Sistema usou dados locais (pode estar desatualizado) |

**Exemplo:**
- Ano 2026: R$ 100,00 (↓ -95,29%) → Você pagará 95% MENOS que hoje
- Ano 2033: R$ 880,00 (↓ -58,59%) → Você pagará 58% MENOS que hoje

---

### Passo 5: Fechar o Sistema

1. Volte na janela preta do Prompt de Comando
2. Pressione `Ctrl + C`
3. Feche a janela

---

## Interface de Chat (Modo Conversacional)

Se preferir **conversar** com o sistema em vez de preencher formulários:

1. Execute: `streamlit run app_chat.py`
2. Digite perguntas em linguagem natural, por exemplo:
   - "Quanto vou pagar de imposto num frete de 15 mil de SP pra RJ?"
   - "E se for Simples Nacional?"
   - "Qual a alíquota de CBS em 2026?"
   - "Por que pago menos em 2026?"
3. O agente lembra o contexto da conversa (não precisa repetir tudo)
4. Use a **barra lateral** para ver os dados acumulados da sessão

> 💡 O modo chat funciona melhor com a chave da OpenAI configurada (`.env`), mas também funciona sem ela usando extração por padrões.

---

## Interface Alternativa (API — Para Usuários Técnicos)

Se preferir usar a API REST (interface mais técnica, tipo Swagger):

1. Em vez de `streamlit run app_ui.py`, execute:
   ```
   uvicorn src.api.main:app --reload --port 8000
   ```
2. Abra no navegador: http://localhost:8000/docs
3. Endpoints disponíveis:
   - `POST /simular` — simulação completa (auto-aprovada)
   - `POST /simular-review` — simulação com aprovação humana obrigatória
   - `POST /review/{thread_id}` — aprovar ou rejeitar resultado pendente
   - `GET /resultado/{thread_id}` — consultar resultado persistido
   - `GET /observabilidade/{thread_id}` — timeline de execução

---

## Perguntas Frequentes

### "Deu erro ao instalar"
- Verifique se marcou "Add Python to PATH" na instalação do Python
- Tente fechar o Prompt e abrir novamente

### "O navegador não abriu"
- Acesse manualmente: http://localhost:8501 (Streamlit) ou http://localhost:8000/docs (API)

### "Aparece uma janela preta e fecha sozinha"
- Você precisa navegar até a pasta correta primeiro (`cd C:\LogitaxAgent\...`)

### "Os valores estão certos?"
- O sistema usa a tabela oficial da LC 214/2025
- Os cálculos são 100% matemáticos (a IA NÃO calcula impostos)
- Valores de IBS para 2033 são estimativas (dependem do Senado)

### "O que é Lucro Real / Presumido / Simples?"
- **Simples Nacional**: Empresas menores, faturamento até R$ 4,8 mi/ano
- **Lucro Presumido**: Empresas médias
- **Lucro Real**: Empresas maiores (geralmente pagam menos no regime novo)
- **Não sabe qual é? Pergunte ao contador!**

### "Posso confiar no resultado para tomar decisões?"
- Use como **referência** para planejamento, não como valor definitivo
- As alíquotas finais dependem de resolução do Senado (prevista até 2035)
- Sempre consulte um contador para decisões contratuais

---

## Resumo Rápido

```
1. Abra o Prompt de Comando (cmd)
2. cd C:\LogitaxAgent\projeto-avaliativo-logitaxAgent-main
3. streamlit run app_ui.py
4. Use a aba "Simulador" para formulário OU "Chat" para conversar
5. Veja os resultados (tabela comparativa, créditos, base legal)
6. Compare regimes tributários com 1 clique
7. Exporte ou aprove o resultado
8. Ctrl+C para fechar
```
