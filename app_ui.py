"""Interface gráfica do LogitaxAgent — Streamlit.

Execute com: streamlit run app_ui.py
"""

import asyncio
import os

import streamlit as st

# Ensure local mode for Tool_Transicao (no HTTP needed)
os.environ.setdefault("TOOL_TRANSICAO_MODE", "local")

from src.graph.graph import build_graph  # noqa: E402
from src.models.operacao import OperacaoFrete  # noqa: E402

st.set_page_config(page_title="LogitaxAgent — Simulador IBS/CBS", page_icon="🧮", layout="wide")

st.title("🧮 LogitaxAgent — Simulador de Impacto IBS/CBS")
st.markdown(
    "Calcule quanto sua empresa de frete vai pagar de imposto "
    "**antes e depois** da Reforma Tributária."
)

st.divider()

# --- Formulário ---
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


# --- Helper to run async graph ---
async def _run_graph(initial_state: dict) -> dict:
    """Execute the LangGraph StateGraph asynchronously."""
    graph = build_graph()
    compiled = graph.compile(interrupt_before=[])
    return await compiled.ainvoke(initial_state)


# --- Botão de simulação ---
if st.button("🚀 Simular Impacto Tributário", type="primary", use_container_width=True):
    with st.spinner("Executando simulação via LangGraph..."):
        # Validate operation
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

        # Prepare initial state for the graph
        initial_state = {
            "operacao": operacao,
            "thread_id": f"streamlit-{id(st.session_state)}",
            "tentativas_reclassificacao": 0,
            "revisao_manual": False,
            "resultados_por_ano": [],
            "trechos_rag": [],
            "justificativa": None,
            "alertas": [],
            "aprovado_humano": True,  # Auto-approve for UI flow
        }

        # Execute the full graph
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

            # Show if data is official or estimated
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

            # Regime Atual
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
                else:
                    st.markdown(f"Total: R$ {rd['valor_tributo_atual']:.2f}")

            # Regime Novo
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
                else:
                    st.markdown(f"Total: R$ {rd['valor_tributo_novo']:.2f}")

            # Delta
            delta = rd["delta_percentual"]
            economia = rd.get("economia_ou_aumento", "")
            if economia:
                st.markdown(f"**Resultado:** {economia}")

    # --- Justificativa legislativa (se disponível) ---
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

    # --- Como ler os resultados ---
    st.divider()
    with st.expander("📖 Como ler os resultados"):
        st.markdown("""
        - **Valor mostrado**: quanto pagará de imposto no regime novo
        - **Percentual verde (↓)**: você pagará **menos** imposto (economia)
        - **Percentual vermelho (↑)**: você pagará **mais** imposto (aumento)
        - **"Atual"**: quanto paga hoje (PIS 1,65% + COFINS 7,6% + ICMS 12% = 21,25%)
        - **CBS**: Contribuição sobre Bens e Serviços (federal, substitui PIS/COFINS)
        - **IBS**: Imposto sobre Bens e Serviços (estadual/municipal, substitui ICMS)
        - **ICMS residual**: ICMS que ainda incide durante a transição (diminui a cada ano)
        """)

# --- Rodapé ---
st.divider()
st.caption(
    "LogitaxAgent v0.1.0 — Sistema híbrido agêntico para simulação de impacto IBS/CBS. "
    "Os valores são estimativas baseadas na LC 214/2025."
)
