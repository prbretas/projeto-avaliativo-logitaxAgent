"""Interface unificada do LogitaxAgent — Streamlit (Simulador + Chat).

Execute com: streamlit run app_ui.py
"""

import asyncio
import os
import uuid

import streamlit as st
from dotenv import load_dotenv

# Load .env file (LLM config, paths, etc.)
load_dotenv()

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

# --- Sidebar: info do LLM ---
with st.sidebar:
    st.subheader("🤖 Modelo de IA")
    _llm_model = os.environ.get("LLM_MODEL_NAME", "não configurado")
    _llm_endpoint = os.environ.get("LLM_ENDPOINT", "não configurado")
    _llm_key = os.environ.get("OPENAI_API_KEY", "")

    # Detect provider from endpoint
    if "ollama" in _llm_endpoint or _llm_key.lower() == "ollama":
        _provider = "Ollama (local)"
    elif "groq" in _llm_endpoint:
        _provider = "Groq (nuvem)"
    elif "openai" in _llm_endpoint:
        _provider = "OpenAI"
    elif _llm_key:
        _provider = "Customizado"
    else:
        _provider = "Não configurado"

    st.caption(f"**Provider:** {_provider}")
    st.caption(f"**Modelo:** {_llm_model}")

    if not _llm_key:
        st.warning("LLM não configurado. Veja MANUAL_CONFIGURACAO_LLM.md")
    else:
        st.success("LLM ativo")

    st.divider()

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

        # Generate comment locally if graph didn't produce one
        if not comentario and resultados:
            from src.graph.nodes.generate_justification import _gerar_comentario_agente

            resultados_dicts = [
                r.model_dump() if hasattr(r, "model_dump") else r for r in resultados
            ]
            comentario = _gerar_comentario_agente(resultados_dicts, operacao)

        if not resultados:
            st.error("Nenhum resultado retornado.")
            st.stop()

        st.success("✅ Simulação concluída com sucesso!")

        # --- Resumo dos parâmetros selecionados (#75) ---
        regime_labels = {
            "lucro_real": "Lucro Real",
            "lucro_presumido": "Lucro Presumido",
            "simples_nacional": "Simples Nacional",
        }
        modal_labels = {
            "rodoviario": "🚛 Rodoviário",
            "aereo": "✈️ Aéreo",
            "ferroviario": "🚂 Ferroviário",
            "aquaviario": "🚢 Aquaviário",
        }
        st.markdown(
            f"**Simulação:** Frete de **R$ {valor_frete:,.2f}** | "
            f"Rota **{origem_uf} → {destino_uf}** | "
            f"Regime **{regime_labels.get(regime, regime)}** | "
            f"Modal {modal_labels.get(modal, modal)} | "
            f"Ano referência **{ano_ref}**"
        )
        st.caption(
            "ℹ️ O modal não afeta a alíquota IBS/CBS para transporte de carga "
            "(LC 214/2025, art. 284). A diferença vem da rota (UFs) e do regime tributário."
        )

        # --- Comentário analítico do agente ---
        if comentario:
            st.divider()
            st.markdown("### 🤖 Análise do Agente")
            st.info(comentario)

        # --- Cards de resultado por ano (scroll horizontal) ---
        st.divider()
        st.subheader("📊 Resultado por Ano de Transição")

        # Use a horizontal scrollable container
        card_html = '<div style="display:flex; overflow-x:auto; gap:16px; padding:8px 0;">'
        for r in resultados:
            rd = r.model_dump() if hasattr(r, "model_dump") else r
            delta = rd["delta_percentual"]
            ano = rd["ano"]
            novo = rd["valor_tributo_novo"]
            atual = rd["valor_tributo_atual"]
            is_selected = ano == ano_ref

            # Colors
            if delta < 0:
                delta_color = "#4CAF50"  # green
                delta_icon = "↓"
            else:
                delta_color = "#f44336"  # red
                delta_icon = "↑"

            border = "2px solid #FFD700" if is_selected else "1px solid #333"
            star = "⭐ " if is_selected else ""

            card_html += f"""
            <div style="min-width:160px; padding:16px; border-radius:8px;
                        border:{border}; background:#1a1a2e; text-align:center;">
                <div style="font-size:12px; color:#aaa;">{star}Ano {ano}</div>
                <div style="font-size:22px; font-weight:bold; margin:8px 0;">
                    R$ {novo:,.2f}
                </div>
                <div style="color:{delta_color}; font-size:14px; font-weight:bold;">
                    {delta_icon} {delta:+.2f}%
                </div>
                <div style="font-size:11px; color:#888; margin-top:6px;">
                    Atual: R$ {atual:,.2f}
                </div>
            </div>"""

        card_html += "</div>"
        st.markdown(card_html, unsafe_allow_html=True)

        # --- Tabela comparativa de impostos ---
        st.divider()
        st.subheader("📋 Comparativo: Quanto Você Paga Hoje vs. Regime Novo")
        st.caption("Valores em R$ para o frete informado.")

        import pandas as pd

        # Credit factor by regime
        credit_pct = {"lucro_real": 1.0, "lucro_presumido": 0.5, "simples_nacional": 0.0}
        credit_factor = credit_pct.get(regime, 0.0)
        credit_label = {
            "lucro_real": "100% (Lucro Real)",
            "lucro_presumido": "50% (Presumido)",
            "simples_nacional": "0% (Simples)",
        }.get(regime, "0%")

        table_rows = []
        for r in resultados:
            rd = r.model_dump() if hasattr(r, "model_dump") else r
            dn = rd.get("detalhe_regime_novo", {})
            ano = rd["ano"]
            atual = rd["valor_tributo_atual"]
            novo = rd["valor_tributo_novo"]
            delta = rd["delta_percentual"]
            economia = rd.get("economia_ou_aumento", "")

            # Calculate credit (#73)
            cbs_val = dn.get("cbs_valor", 0)
            ibs_val = dn.get("ibs_valor", 0)
            credito = round((cbs_val + ibs_val) * credit_factor, 2)
            custo_liquido = round(novo - credito, 2)

            table_rows.append(
                {
                    "Ano": f"{'→ ' if ano == ano_ref else ''}{ano}",
                    "Imposto Hoje": atual,
                    "Imposto Novo (bruto)": novo,
                    "Crédito IBS/CBS": credito,
                    "Custo Líquido": custo_liquido,
                    "Variação": delta,
                    "Resultado": economia,
                }
            )

        df = pd.DataFrame(table_rows)

        def _style_comparativo(row):
            """Green for economy, red for increase."""
            styles = [""] * len(row)
            var_idx = df.columns.get_loc("Variação")
            res_idx = df.columns.get_loc("Resultado")
            liq_idx = df.columns.get_loc("Custo Líquido")
            if row["Variação"] < 0:
                styles[var_idx] = "color: #4CAF50; font-weight: bold"
                styles[res_idx] = "color: #4CAF50"
                styles[liq_idx] = "color: #4CAF50; font-weight: bold"
            elif row["Variação"] > 0:
                styles[var_idx] = "color: #f44336; font-weight: bold"
                styles[res_idx] = "color: #f44336"
                styles[liq_idx] = "color: #f44336; font-weight: bold"
            return styles

        styled_df = df.style.apply(_style_comparativo, axis=1).format(
            {
                "Imposto Hoje": "R$ {:,.2f}",
                "Imposto Novo (bruto)": "R$ {:,.2f}",
                "Crédito IBS/CBS": "R$ {:,.2f}",
                "Custo Líquido": "R$ {:,.2f}",
                "Variação": "{:+.2f}%",
            }
        )
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        st.caption(f"Crédito aplicado: {credit_label}")

        # Detailed breakdown with color coding
        with st.expander("🔍 Ver detalhamento por imposto (PIS, COFINS, ICMS, CBS, IBS)"):
            st.markdown(
                "🔵 **Regime Atual** (PIS + COFINS + ICMS) &nbsp;|&nbsp; "
                "🟠 **Regime Novo** (CBS + IBS + ICMS residual)",
            )
            detail_rows = []
            for r in resultados:
                rd = r.model_dump() if hasattr(r, "model_dump") else r
                da = rd.get("detalhe_regime_atual", {})
                dn = rd.get("detalhe_regime_novo", {})

                def _fmt(valor, pct):
                    """Format value with percentage, or — if zero."""
                    if valor == 0 and pct == 0:
                        return "—"
                    return f"R$ {valor:,.2f} ({pct}%)"

                detail_rows.append(
                    {
                        "Ano": rd["ano"],
                        "PIS": _fmt(
                            da.get("pis_valor", 0),
                            da.get("pis_aliquota_pct", 0),
                        ),
                        "COFINS": _fmt(
                            da.get("cofins_valor", 0),
                            da.get("cofins_aliquota_pct", 0),
                        ),
                        "ICMS": _fmt(
                            da.get("icms_valor", 0),
                            da.get("icms_aliquota_pct", 0),
                        ),
                        "Total Atual": f"R$ {da.get('total', 0):,.2f}",
                        "CBS": _fmt(
                            dn.get("cbs_valor", 0),
                            dn.get("cbs_aliquota_pct", 0),
                        ),
                        "IBS": _fmt(
                            dn.get("ibs_valor", 0),
                            dn.get("ibs_aliquota_pct", 0),
                        ),
                        "ICMS Residual": _fmt(
                            dn.get("icms_residual_valor", 0),
                            dn.get("icms_residual_aliquota_pct", 0),
                        ),
                        "Total Novo": f"R$ {dn.get('total', 0):,.2f}",
                    }
                )
            df_detail = pd.DataFrame(detail_rows)

            def _color_detail_cols(col):
                if col.name in ("PIS", "COFINS", "ICMS", "Total Atual"):
                    return ["color: #64B5F6"] * len(col)
                elif col.name in ("CBS", "IBS", "ICMS Residual", "Total Novo"):
                    return ["color: #FFA726"] * len(col)
                return [""] * len(col)

            styled_detail = df_detail.style.apply(_color_detail_cols)
            st.dataframe(styled_detail, use_container_width=True, hide_index=True)

        # --- Base Legal e Notas da Transição (#70) ---
        with st.expander("📜 Base Legal e Cronograma da Transição"):
            for r in resultados:
                rd = r.model_dump() if hasattr(r, "model_dump") else r
                ano = rd["ano"]
                # Get base_legal from tool response (stored in fonte_tool metadata)
                base_legal = rd.get("base_legal", "")
                nota = rd.get("nota_transicao", "")
                split = rd.get("split_payment", False)

                if not base_legal:
                    # Fallback: lookup from local table
                    import json
                    from pathlib import Path

                    _data_path = Path("data/tabela_transicao_local.json")
                    if _data_path.exists():
                        _tabela = json.loads(_data_path.read_text(encoding="utf-8"))
                        _entry = next((t for t in _tabela if t["ano"] == ano), {})
                        base_legal = _entry.get("base_legal", "")
                        nota = _entry.get("nota_transicao", "")
                        split = _entry.get("split_payment", False)

                marker = "→ " if ano == ano_ref else ""
                st.markdown(f"**{marker}{ano}** — {base_legal}")
                if nota:
                    st.caption(f"  {nota}")
                if split:
                    st.caption("  💳 Split payment ativo: tributo retido no pagamento")

        # --- Justificativa legislativa ---
        if justificativa:
            st.divider()
            st.subheader("📜 Justificativa Legislativa (IA)")
            st.markdown(justificativa)
            st.caption(
                "Texto gerado por IA com base em trechos da LC 214/2025. "
                "Os cálculos numéricos são determinísticos."
            )

        # --- Alertas (filtrar alertas técnicos, mostrar apenas relevantes) ---
        alertas_usuario = [a for a in alertas if "fallback" in a.lower() or "dados" in a.lower()]
        if alertas_usuario:
            st.divider()
            for alerta in alertas_usuario:
                st.caption(f"ℹ️ {alerta}")

        # --- Alerta cClassTrib (#71) ---
        st.divider()
        st.subheader("⚠️ Obrigação Acessória — CT-e")
        if regime == "simples_nacional":
            st.warning(
                "**Simples Nacional:** O preenchimento do campo `cClassTrib` no CT-e é "
                "**facultativo em 2026** e **obrigatório a partir de 01/01/2027**. "
                "Prepare-se para a transição."
            )
        else:
            st.error(
                "**Atenção:** A partir de **agosto/2026**, o campo `cClassTrib` é "
                "**obrigatório** em todos os CT-e emitidos por empresas do regime regular. "
                "CT-e sem este campo será **rejeitado pela SEFAZ**."
            )
        st.caption("Fonte: NT 2025.001 do CT-e + LC 214/2025, art. 284")

        # --- Comparação entre regimes (#72) ---
        st.divider()
        if st.button(
            "🔄 Comparar os 3 Regimes Tributários para esta rota",
            use_container_width=True,
        ):
            with st.spinner("Simulando Lucro Real, Lucro Presumido e Simples Nacional..."):
                import pandas as pd

                regimes_para_comparar = [
                    ("lucro_real", "Lucro Real"),
                    ("lucro_presumido", "Lucro Presumido"),
                    ("simples_nacional", "Simples Nacional"),
                ]
                comparacao_rows = []

                for reg_key, reg_label in regimes_para_comparar:
                    try:
                        op_comp = OperacaoFrete(
                            modal=modal,
                            origem_uf=origem_uf,
                            destino_uf=destino_uf,
                            regime_tributario=reg_key,
                            valor_frete=valor_frete,
                            data_referencia=f"{ano_ref}-06-15",
                        )
                        state_comp = {
                            "operacao": op_comp,
                            "thread_id": f"comp-{uuid.uuid4()}",
                            "tentativas_reclassificacao": 0,
                            "revisao_manual": False,
                            "resultados_por_ano": [],
                            "trechos_rag": [],
                            "justificativa": None,
                            "alertas": [],
                            "aprovado_humano": True,
                        }
                        res_comp = asyncio.run(_run_graph(state_comp))

                        for r in res_comp.get("resultados_por_ano", []):
                            rd = r.model_dump() if hasattr(r, "model_dump") else r
                            comparacao_rows.append(
                                {
                                    "Regime": reg_label,
                                    "Ano": rd["ano"],
                                    "Imposto Novo (R$)": rd["valor_tributo_novo"],
                                    "Variação (%)": rd["delta_percentual"],
                                }
                            )
                    except Exception:
                        pass

            if comparacao_rows:
                st.subheader("📊 Comparação entre Regimes")
                st.caption(f"Rota {origem_uf}→{destino_uf} | Frete R$ {valor_frete:,.2f}")
                df_comp = pd.DataFrame(comparacao_rows)
                # Pivot: anos como linhas, regimes como colunas
                df_pivot = df_comp.pivot_table(
                    index="Ano",
                    columns="Regime",
                    values="Imposto Novo (R$)",
                    aggfunc="first",
                )

                def _color_min(row):
                    """Highlight minimum value (best regime) in green."""
                    styles = [""] * len(row)
                    min_idx = row.values.argmin()
                    styles[min_idx] = "color: #4CAF50; font-weight: bold"
                    return styles

                styled_comp = df_pivot.style.apply(_color_min, axis=1).format("R$ {:,.2f}")
                st.dataframe(styled_comp, use_container_width=True)
                st.caption("🟢 Verde = regime mais vantajoso para aquele ano.")

        # --- Ações ---
        st.divider()
        st.subheader("📤 Exportar Resultado")
        st.markdown(
            "Exporte este resultado para seu sistema (ERP/TMS) ou envie para aprovação do gestor."
        )

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
            if st.button("📤 Exportar e Aprovar", type="primary", use_container_width=True):
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
            if st.button("🔄 Nova Simulação", use_container_width=True):
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
                st.info("🔄 Resultado descartado. Ajuste os parâmetros e simule novamente.")


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
