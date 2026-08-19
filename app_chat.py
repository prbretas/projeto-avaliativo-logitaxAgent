"""Interface conversacional do LogitaxAgent — Streamlit Chat.

Execute com: streamlit run app_chat.py

O agente interpreta perguntas em linguagem natural, extrai parâmetros,
executa simulações via LangGraph e responde sobre legislação via RAG.
"""

import asyncio
import os
import uuid

import streamlit as st

os.environ.setdefault("TOOL_TRANSICAO_MODE", "local")

from src.chat.intent import extract_intent  # noqa: E402
from src.graph.graph import build_graph  # noqa: E402
from src.graph.nodes.retrieve_context import _retrieve_chunks  # noqa: E402
from src.models.operacao import OperacaoFrete  # noqa: E402

st.set_page_config(page_title="LogitaxAgent — Chat", page_icon="💬", layout="wide")

st.title("💬 LogitaxAgent — Assistente Tributário")
st.caption(
    "Pergunte sobre o impacto da Reforma Tributária no seu frete. "
    'Exemplo: "Quanto vou pagar de imposto num frete de 15 mil de SP pra RJ?"'
)

# --- Session state initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = {}
if "last_result" not in st.session_state:
    st.session_state.last_result = None


# --- Helper functions ---
async def _run_simulation(params: dict) -> dict:
    """Execute the full graph with extracted parameters."""
    operacao = OperacaoFrete(
        modal=params.get("modal", "rodoviario"),
        origem_uf=params["origem_uf"],
        destino_uf=params["destino_uf"],
        regime_tributario=params["regime_tributario"],
        valor_frete=params["valor_frete"],
        data_referencia=f"{params.get('ano', 2026)}-06-15",
    )

    initial_state = {
        "operacao": operacao,
        "thread_id": f"chat-{uuid.uuid4()}",
        "tentativas_reclassificacao": 0,
        "revisao_manual": False,
        "resultados_por_ano": [],
        "trechos_rag": [],
        "justificativa": None,
        "alertas": [],
        "aprovado_humano": True,
    }

    graph = build_graph()
    compiled = graph.compile(interrupt_before=[])
    return await compiled.ainvoke(initial_state)


def _format_simulation_response(result: dict, params: dict) -> str:
    """Format simulation results as a chat-friendly response."""
    resultados = result.get("resultados_por_ano", [])
    if not resultados:
        return "Não consegui gerar resultados para essa simulação. Tente novamente."

    origem = params.get("origem_uf", "?")
    destino = params.get("destino_uf", "?")
    valor = params.get("valor_frete", 0)
    regime = params.get("regime_tributario", "lucro_real")
    regime_label = {
        "lucro_real": "Lucro Real",
        "lucro_presumido": "Lucro Presumido",
        "simples_nacional": "Simples Nacional",
    }.get(regime, regime)

    lines = [
        f"**Simulação: frete R$ {valor:,.2f} de {origem} → {destino} ({regime_label})**\n",
        "| Ano | Imposto Atual | Imposto Novo | Variação |",
        "|-----|--------------|-------------|----------|",
    ]

    for r in resultados:
        rd = r.model_dump() if hasattr(r, "model_dump") else r
        ano = rd["ano"]
        atual = rd["valor_tributo_atual"]
        novo = rd["valor_tributo_novo"]
        delta = rd["delta_percentual"]
        emoji = "📉" if delta < 0 else "📈"
        lines.append(f"| {ano} | R$ {atual:,.2f} | R$ {novo:,.2f} | {emoji} {delta:+.2f}% |")

    # Add comentario if available
    comentario = result.get("comentario_agente", "")
    if comentario:
        lines.append(f"\n**Análise:** {comentario}")

    return "\n".join(lines)


def _format_missing_params_question(missing: list[str], params: dict) -> str:
    """Generate a follow-up question for missing parameters."""
    questions = []
    for p in missing:
        if p == "valor_frete":
            questions.append("Qual o **valor do frete** (em R$)?")
        elif p == "origem_uf":
            questions.append("Qual o **estado de origem** (ex: SP, RJ, MG)?")
        elif p == "destino_uf":
            questions.append("Qual o **estado de destino** (ex: BA, RJ, SP)?")
        elif p == "regime_tributario":
            questions.append(
                "Qual o **regime tributário** da empresa? "
                "(Lucro Real, Lucro Presumido ou Simples Nacional)"
            )

    intro = "Para simular, preciso de mais algumas informações:\n\n"
    return intro + "\n".join(f"- {q}" for q in questions)


def _handle_legislation_query(message: str) -> str:
    """Answer legislation questions using RAG (ChromaDB)."""
    chunks = _retrieve_chunks(ano=2026, regime="lucro_real")

    if chunks:
        citations = []
        for chunk in chunks[:3]:
            citation = chunk.get("citation", "")
            doc = chunk.get("document", "")[:200]
            citations.append(f"**{citation}:** {doc}...")

        return (
            "Encontrei os seguintes trechos legislativos relevantes:\n\n"
            + "\n\n".join(citations)
            + "\n\n*Fonte: LC 214/2025 e legislação complementar.*"
        )
    else:
        return (
            "Não encontrei trechos específicos na base de conhecimento. "
            "Aqui estão as informações básicas:\n\n"
            "- **2026**: Fase-teste com CBS 0,9% + IBS 0,1% = 1,0% (art. 343, LC 214/2025)\n"
            "- **2027-2028**: CBS substitui PIS/COFINS, ICMS integral\n"
            "- **2029-2032**: ICMS vai sendo substituído pelo IBS (10%→40%)\n"
            "- **2033**: ICMS extinto, IBS pleno (~19,1%)\n\n"
            "Para detalhes específicos, consulte a LC 214/2025 no planalto.gov.br."
        )


def _handle_explanation(last_result: dict | None) -> str:
    """Explain the last simulation result."""
    if not last_result:
        return (
            "Não há resultado anterior para explicar. "
            "Faça uma simulação primeiro! Exemplo: "
            '"Simule um frete de 10 mil de SP pra RJ no Lucro Real"'
        )

    comentario = last_result.get("comentario_agente", "")
    if comentario:
        return f"**Explicação do último resultado:**\n\n{comentario}"

    return (
        "O resultado mostra a comparação entre o imposto que você paga hoje "
        "(PIS + COFINS + ICMS) e o que pagará no regime novo (CBS + IBS). "
        "Valores negativos (verde) significam economia; positivos (vermelho) significam aumento."
    )


# --- Display chat history ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat input ---
if prompt := st.chat_input("Pergunte sobre impostos no frete..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Extract intent
    intent = extract_intent(prompt, st.session_state.context)

    # Process based on intent
    with st.chat_message("assistant"):
        if intent.intent == "saudacao":
            response = (
                "Olá! Sou o LogitaxAgent, seu assistente para simulação de "
                "impacto da Reforma Tributária no frete. 🧮\n\n"
                "Posso ajudar com:\n"
                '- **Simulação**: "Quanto vou pagar de imposto num frete de 10 mil de SP pra RJ?"\n'
                '- **Comparação**: "Compara Lucro Real com Simples Nacional"\n'
                '- **Legislação**: "Qual a alíquota de CBS em 2026?"\n\n'
                "Como posso ajudar?"
            )
            st.markdown(response)

        elif intent.intent == "legislacao":
            with st.spinner("Consultando legislação..."):
                response = _handle_legislation_query(prompt)
            st.markdown(response)

        elif intent.intent == "explicar":
            response = _handle_explanation(st.session_state.last_result)
            st.markdown(response)

        elif intent.intent in ("simular", "comparar"):
            if not intent.is_complete_for_simulation():
                # Ask for missing params
                response = _format_missing_params_question(intent.missing_params, intent.params)
                st.markdown(response)
                # Save partial params to context for next message
                st.session_state.context.update(intent.params)
            else:
                # Execute simulation
                with st.spinner("Executando simulação via LangGraph..."):
                    try:
                        result = asyncio.run(_run_simulation(intent.params))
                        response = _format_simulation_response(result, intent.params)
                        # Save result and context
                        st.session_state.last_result = result
                        st.session_state.context.update(intent.params)
                    except Exception as e:
                        response = f"Erro na simulação: {e}"

                st.markdown(response)

        else:
            response = (
                "Não entendi completamente. Posso ajudar com:\n"
                "- Simulação de impostos no frete\n"
                "- Perguntas sobre legislação (LC 214/2025)\n"
                "- Explicação de resultados\n\n"
                'Tente algo como: "Simule um frete de 20 mil de MG pra BA no Simples Nacional"'
            )
            st.markdown(response)

    # Save assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})

# --- Sidebar with context info ---
with st.sidebar:
    st.subheader("📋 Contexto da Sessão")
    ctx = st.session_state.context
    if ctx:
        if "valor_frete" in ctx:
            st.write(f"💰 Valor: R$ {ctx['valor_frete']:,.2f}")
        if "origem_uf" in ctx:
            st.write(f"📍 Origem: {ctx['origem_uf']}")
        if "destino_uf" in ctx:
            st.write(f"📍 Destino: {ctx['destino_uf']}")
        if "regime_tributario" in ctx:
            label = {
                "lucro_real": "Lucro Real",
                "lucro_presumido": "Lucro Presumido",
                "simples_nacional": "Simples Nacional",
            }.get(ctx["regime_tributario"], ctx["regime_tributario"])
            st.write(f"🏢 Regime: {label}")
        if "modal" in ctx:
            st.write(f"🚛 Modal: {ctx['modal']}")
    else:
        st.write("Nenhuma simulação realizada ainda.")

    st.divider()
    if st.button("🗑️ Limpar conversa"):
        st.session_state.messages = []
        st.session_state.context = {}
        st.session_state.last_result = None
        st.rerun()

    st.divider()
    st.caption(
        "💡 **Dica:** Use o formulário em `streamlit run app_ui.py` "
        "para simulação visual com gráficos."
    )
