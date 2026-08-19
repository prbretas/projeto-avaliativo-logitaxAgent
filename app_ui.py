"""Interface unificada do LogitaxAgent — Streamlit (Simulador + Chat).

Execute com: streamlit run app_ui.py
"""

import asyncio
import os
import uuid

import streamlit as st

# Ensure local mode for Tool_Transicao (no HTTP needed)
os.environ.setdefault("TOOL_TRANSICAO_MODE", "local")

from src.chat.intent import extract_intent  # noqa: E402
from src.graph.graph import build_graph  # noqa: E402
from src.graph.nodes.retrieve_context import _retrieve_chunks  # noqa: E402
from src.models.operacao import OperacaoFrete  # noqa: E402
from src.persistence.checkpointer import SessionCheckpointer  # noqa: E402

st.set_page_config(page_title="LogitaxAgent — Simulador IBS/CBS", page_icon="🧮", layout="wide")

st.title("🧮 LogitaxAgent — Simulador de Impacto IBS/CBS")
st.markdown(
    "Calcule quanto sua empresa de frete vai pagar de imposto "
    "**antes e depois** da Reforma Tributária."
)

# --- Tabs: Simulador | Chat ---
tab_simular, tab_chat = st.tabs(["📊 Simulador", "💬 Chat com o Agente"])


# --- Helper to run async graph ---
async def _run_graph(initial_state: dict) -> dict:
    """Execute the LangGraph StateGraph asynchronously."""
    graph = build_graph()
    compiled = graph.compile(interrupt_before=[])
    return await compiled.ainvoke(initial_state)


# ============================================================
# TAB 1: SIMULADOR (formulário)
# ============================================================
with tab_simular:
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Dados da Operação")

        modal = st.selectbox(
            "Tipo de Transporte (Modal)",
            options=["rodoviario", "aereo", "ferroviario", "aquaviario"],
            format_func=lambda x: {
                "rodoviario": "🚛 Rodoviário",
                "aereo": "✈️ Aéreo",
                "ferroviario": "🚂 Ferroviário",
                "aquaviario": "🚢 Aquaviário",
            }[x],
            help="Tipo de transporte para o CT-e. Não afeta a alíquota IBS/CBS "
            "(que é uniforme por tipo de serviço), mas é registrado na operação.",
        )

        UFS = [
            "AC",
            "AL",
            "AM",
            "AP",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MG",
            "MS",
            "MT",
            "PA",
            "PB",
            "PE",
            "PI",
            "PR",
            "RJ",
            "RN",
            "RO",
            "RR",
            "RS",
            "SC",
            "SE",
            "SP",
            "TO",
        ]

        origem_uf = st.selectbox("Estado de Origem", options=UFS, index=UFS.index("SP"))
        destino_uf = st.selectbox("Estado de Destino", options=UFS, index=UFS.index("RJ"))

        st.caption(
            "💡 O ICMS interestadual varia por rota: Sul/Sudeste→Sul/Sudeste = 12%, "
            "Sul/Sudeste→N/NE/CO = 7%. Mude as UFs para ver a diferença."
        )

    with col2:
        st.subheader("Dados Fiscais")

        regime = st.selectbox(
            "Regime Tributário da Empresa",
            options=["lucro_real", "lucro_presumido", "simples_nacional"],
            format_func=lambda x: {
                "lucro_real": "Lucro Real",
                "lucro_presumido": "Lucro Presumido",
                "simples_nacional": "Simples Nacional",
            }[x],
            help="Pergunte ao contador da sua empresa se não souber.",
        )

        valor_frete = st.number_input(
            "Valor do Frete (R$)",
            min_value=0.01,
            max_value=999999999.99,
            value=10000.00,
            step=1000.00,
            format="%.2f",
        )

        ano_ref = st.selectbox(
            "Ano de Referência",
            options=[2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033],
            index=0,
            help="Ano da transição que deseja simular",
        )

    st.divider()

    # --- Botão de simulação ---
    if st.button("🚀 Simular Impacto Tributário", type="primary", use_container_width=True):
        with st.spinner("Executando simulação via LangGraph..."):
            try:
                operacao = OperacaoFrete(
                    modal=modal,
                    origem_uf=origem_uf,
                    destino_uf=destino_uf,
                    regime_tributario=regime,
                    valor_frete=valor_frete,
                    data_referencia=f"{ano_ref}-06-15",
                )
            except Exception as e:
                st.error(f"❌ Erro na validação dos dados: {e}")
                st.stop()

            initial_state = {
                "operacao": operacao,
                "thread_id": f"ui-{uuid.uuid4()}",
                "tentativas_reclassificacao": 0,
                "revisao_manual": False,
                "resultados_por_ano": [],
                "trechos_rag": [],
                "justificativa": None,
                "alertas": [],
                "aprovado_humano": True,
            }

            try:
                result = asyncio.run(_run_graph(initial_state))
            except Exception as e:
                st.error(f"❌ Erro na execução do grafo: {e}")
                st.stop()

        # --- Extract results ---
        resultados = result.get("resultados_por_ano", [])
        comentario = result.get("comentario_agente", "")
        justificativa = result.get("justificativa")
        alertas = result.get("alertas", [])

        if not resultados:
            st.error("Nenhum resultado retornado.")
            st.stop()

        st.success("✅ Simulação concluída com sucesso!")

        # --- Comentário analítico do agente ---
        if comentario:
            st.divider()
            st.markdown("### 🤖 Análise do Agente")
            st.info(comentario)

        # --- Cards de resultado por ano ---
        st.divider()
        st.subheader("📊 Resultado por Ano de Transição")

        cols = st.columns(len(resultados))
        for i, r in enumerate(resultados):
            rd = r.model_dump() if hasattr(r, "model_dump") else r
            with cols[i]:
                delta = rd["delta_percentual"]
                st.metric(
                    label=f"Ano {rd['ano']}",
                    value=f"R$ {rd['valor_tributo_novo']:.2f}",
                    delta=f"{delta:.2f}%",
                    delta_color="inverse",
                )
                st.caption(f"Atual: R$ {rd['valor_tributo_atual']:.2f}")
                if rd.get("fallback_usado"):
                    st.caption("⚠️ Dados de fallback")
                detalhe_novo = rd.get("detalhe_regime_novo", {})
                if detalhe_novo and not detalhe_novo.get("oficial", True):
                    st.caption("📊 Alíquotas estimadas")

        # --- Detalhamento de impostos ---
        st.divider()
        st.subheader("📋 Detalhamento de Impostos")

        for r in resultados:
            rd = r.model_dump() if hasattr(r, "model_dump") else r
            ano = rd["ano"]
            with st.expander(f"📅 Ano {ano} — Detalhes"):
                col_atual, col_novo = st.columns(2)
                detalhe_atual = rd.get("detalhe_regime_atual", {})
                with col_atual:
                    st.markdown("**Regime Atual (PIS+COFINS+ICMS)**")
                    if detalhe_atual:
                        st.markdown(
                            f"- PIS: {detalhe_atual.get('pis_aliquota_pct', 0)}% "
                            f"= R$ {detalhe_atual.get('pis_valor', 0):.2f}"
                        )
                        st.markdown(
                            f"- COFINS: {detalhe_atual.get('cofins_aliquota_pct', 0)}% "
                            f"= R$ {detalhe_atual.get('cofins_valor', 0):.2f}"
                        )
                        st.markdown(
                            f"- ICMS: {detalhe_atual.get('icms_aliquota_pct', 0)}% "
                            f"= R$ {detalhe_atual.get('icms_valor', 0):.2f}"
                        )
                        st.markdown(f"- **Total: R$ {detalhe_atual.get('total', 0):.2f}**")

                detalhe_novo = rd.get("detalhe_regime_novo", {})
                with col_novo:
                    st.markdown("**Regime Novo (IBS+CBS+ICMS residual)**")
                    if detalhe_novo:
                        st.markdown(
                            f"- CBS: {detalhe_novo.get('cbs_aliquota_pct', 0)}% "
                            f"= R$ {detalhe_novo.get('cbs_valor', 0):.2f}"
                        )
                        st.markdown(
                            f"- IBS: {detalhe_novo.get('ibs_aliquota_pct', 0)}% "
                            f"= R$ {detalhe_novo.get('ibs_valor', 0):.2f}"
                        )
                        st.markdown(
                            f"- ICMS residual: "
                            f"{detalhe_novo.get('icms_residual_aliquota_pct', 0)}% "
                            f"= R$ {detalhe_novo.get('icms_residual_valor', 0):.2f}"
                        )
                        st.markdown(f"- **Total: R$ {detalhe_novo.get('total', 0):.2f}**")
                        if not detalhe_novo.get("oficial", True):
                            st.caption("⚠️ Alíquotas são projeções (não oficiais)")

                economia = rd.get("economia_ou_aumento", "")
                if economia:
                    st.markdown(f"**Resultado:** {economia}")

        # --- Justificativa legislativa ---
        if justificativa:
            st.divider()
            st.subheader("📜 Justificativa Legislativa (IA)")
            st.markdown(justificativa)
            st.caption(
                "Texto gerado por IA com base em trechos da LC 214/2025. "
                "Os cálculos numéricos são determinísticos."
            )

        # --- Alertas ---
        if alertas:
            st.divider()
            st.subheader("⚠️ Alertas")
            for alerta in alertas:
                st.warning(alerta)

        # --- Human Review ---
        st.divider()
        st.subheader("✅ Revisão Humana")
        st.markdown("Revise os valores e decida:")

        thread_id = result.get("thread_id", f"ui-{uuid.uuid4()}")
        _checkpointer = SessionCheckpointer()
        resultados_serialized = [
            r.model_dump() if hasattr(r, "model_dump") else r for r in resultados
        ]
        state_to_persist = {
            "thread_id": thread_id,
            "resultados_por_ano": resultados_serialized,
            "justificativa": justificativa,
            "comentario_agente": comentario,
            "alertas": alertas,
            "aprovado_humano": None,
            "export_status": "awaiting_review",
        }
        _checkpointer.save(thread_id, state_to_persist)

        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("✅ Aprovar", type="primary", use_container_width=True):
                from src.graph.nodes.export_result import (
                    _build_webhook_payload,
                    _send_webhook_sync,
                )
                from src.observability.logger import log_audit_event

                state_to_persist["aprovado_humano"] = True
                webhook_payload = _build_webhook_payload(state_to_persist)
                webhook_sent = _send_webhook_sync(webhook_payload)
                state_to_persist["export_status"] = (
                    "exported" if webhook_sent else "approved_no_webhook"
                )
                _checkpointer.save(thread_id, state_to_persist)
                log_audit_event(
                    thread_id=thread_id,
                    event_type="decisao_humana",
                    node_name="human_review_ui",
                    status="info",
                    details="Aprovado via Streamlit",
                )
                st.success("✅ Aprovado e exportado!")

        with col_reject:
            if st.button("❌ Rejeitar", use_container_width=True):
                from src.observability.logger import log_audit_event

                state_to_persist["aprovado_humano"] = False
                state_to_persist["export_status"] = "rejected"
                _checkpointer.save(thread_id, state_to_persist)
                log_audit_event(
                    thread_id=thread_id,
                    event_type="decisao_humana",
                    node_name="human_review_ui",
                    status="info",
                    details="Rejeitado via Streamlit",
                )
                st.error("❌ Rejeitado. Nenhuma exportação realizada.")


# ============================================================
# TAB 2: CHAT (assistente conversacional)
# ============================================================
with tab_chat:
    st.markdown(
        "Converse com o agente em linguagem natural. "
        'Exemplo: "Quanto vou pagar num frete de 15 mil de SP pra BA no Lucro Real?"'
    )

    # Session state for chat
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_context" not in st.session_state:
        st.session_state.chat_context = {}
    if "chat_last_result" not in st.session_state:
        st.session_state.chat_last_result = None

    # Display chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Pergunte sobre impostos no frete..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        intent = extract_intent(prompt, st.session_state.chat_context)

        with st.chat_message("assistant"):
            if intent.intent == "saudacao":
                response = (
                    "Olá! Sou o LogitaxAgent. Posso simular o impacto tributário "
                    "no seu frete. Diga algo como:\n\n"
                    '- "Simule frete de 20 mil de MG pra SP no Simples"\n'
                    '- "Qual a alíquota de CBS em 2026?"\n'
                    '- "Compara 2026 com 2033"'
                )
                st.markdown(response)

            elif intent.intent == "legislacao":
                with st.spinner("Consultando legislação..."):
                    chunks = _retrieve_chunks(ano=2026, regime="lucro_real")
                if chunks:
                    citations = []
                    for chunk in chunks[:3]:
                        citation = chunk.get("citation", "")
                        doc = chunk.get("document", "")[:200]
                        citations.append(f"**{citation}:** {doc}...")
                    response = (
                        "Encontrei trechos relevantes:\n\n"
                        + "\n\n".join(citations)
                        + "\n\n*Fonte: LC 214/2025*"
                    )
                else:
                    response = (
                        "Informações básicas da transição:\n\n"
                        "- **2026**: Fase-teste CBS 0,9% + IBS 0,1% = 1%\n"
                        "- **2027-2028**: CBS substitui PIS/COFINS, ICMS integral\n"
                        "- **2029-2032**: ICMS substituído gradualmente pelo IBS\n"
                        "- **2033**: ICMS extinto, IBS pleno (~19,1%)"
                    )
                st.markdown(response)

            elif intent.intent == "explicar":
                last = st.session_state.chat_last_result
                if last:
                    comentario = last.get("comentario_agente", "")
                    response = (
                        f"**Explicação:**\n\n{comentario}"
                        if comentario
                        else "O resultado compara imposto atual "
                        "(PIS+COFINS+ICMS) com o novo (CBS+IBS)."
                    )
                else:
                    response = 'Faça uma simulação primeiro! Ex: "Frete de 10 mil SP pra RJ"'
                st.markdown(response)

            elif intent.intent in ("simular", "comparar"):
                if not intent.is_complete_for_simulation():
                    # Ask for missing params
                    questions = []
                    for p in intent.missing_params:
                        if p == "valor_frete":
                            questions.append("Qual o **valor do frete** (R$)?")
                        elif p == "origem_uf":
                            questions.append("Qual o **estado de origem** (ex: SP)?")
                        elif p == "destino_uf":
                            questions.append("Qual o **estado de destino** (ex: RJ)?")
                        elif p == "regime_tributario":
                            questions.append(
                                "Qual o **regime tributário**? (Lucro Real, Presumido ou Simples)"
                            )
                    response = "Preciso de mais dados:\n\n" + "\n".join(f"- {q}" for q in questions)
                    st.session_state.chat_context.update(intent.params)
                    st.markdown(response)
                else:
                    with st.spinner("Simulando..."):
                        try:
                            op = OperacaoFrete(
                                modal=intent.params.get("modal", "rodoviario"),
                                origem_uf=intent.params["origem_uf"],
                                destino_uf=intent.params["destino_uf"],
                                regime_tributario=intent.params["regime_tributario"],
                                valor_frete=intent.params["valor_frete"],
                                data_referencia=f"{intent.params.get('ano', 2026)}-06-15",
                            )
                            state = {
                                "operacao": op,
                                "thread_id": f"chat-{uuid.uuid4()}",
                                "tentativas_reclassificacao": 0,
                                "revisao_manual": False,
                                "resultados_por_ano": [],
                                "trechos_rag": [],
                                "justificativa": None,
                                "alertas": [],
                                "aprovado_humano": True,
                            }
                            res = asyncio.run(_run_graph(state))
                            st.session_state.chat_last_result = res
                            st.session_state.chat_context.update(intent.params)

                            # Format response
                            resultados = res.get("resultados_por_ano", [])
                            p = intent.params
                            lines = [
                                f"**Frete R$ {p['valor_frete']:,.2f} "
                                f"{p['origem_uf']}→{p['destino_uf']}**\n",
                                "| Ano | Atual | Novo | Variação |",
                                "|-----|-------|------|----------|",
                            ]
                            for r in resultados:
                                rd = r.model_dump() if hasattr(r, "model_dump") else r
                                emoji = "📉" if rd["delta_percentual"] < 0 else "📈"
                                lines.append(
                                    f"| {rd['ano']} | R$ {rd['valor_tributo_atual']:,.2f} "
                                    f"| R$ {rd['valor_tributo_novo']:,.2f} "
                                    f"| {emoji} {rd['delta_percentual']:+.2f}% |"
                                )
                            coment = res.get("comentario_agente", "")
                            if coment:
                                lines.append(f"\n**Análise:** {coment}")
                            response = "\n".join(lines)
                        except Exception as e:
                            response = f"Erro na simulação: {e}"
                    st.markdown(response)
            else:
                response = (
                    'Não entendi. Tente: "Simule frete de 10 mil de SP pra RJ" '
                    'ou "Qual a alíquota de 2026?"'
                )
                st.markdown(response)

        st.session_state.chat_messages.append({"role": "assistant", "content": response})

    # Clear chat button
    if st.button("🗑️ Limpar conversa", key="clear_chat"):
        st.session_state.chat_messages = []
        st.session_state.chat_context = {}
        st.session_state.chat_last_result = None
        st.rerun()

# --- Rodapé ---
st.divider()
st.caption(
    "LogitaxAgent v0.1.0 — Assistente conversacional híbrido para simulação de impacto IBS/CBS. "
    "Os valores são estimativas baseadas na LC 214/2025."
)
