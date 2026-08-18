# Prompt: route_intencao

## Descrição

Prompt para classificação de intenção do usuário (caso implementado com LLM).
Atualmente a rota é feita por lógica determinística no node `route_regime`.

**Node:** `src/graph/nodes/route_regime.py`

---

## Prompt Text (Referência)

```
Classifique a intenção do usuário com base no regime tributário informado.

Regimes possíveis:
- simples_nacional → rota: simular_regime_hibrido_simples
- lucro_real → rota: simular_regime_regular
- lucro_presumido → rota: simular_regime_regular

Responda APENAS com o nome da rota.
```

---

## Behavior Rules

| # | Regra |
|---|-------|
| 1 | Classificação determinística (sem LLM na versão atual) |
| 2 | Simples Nacional → sem créditos (credit=0) |
| 3 | Lucro Real / Lucro Presumido → com créditos não-cumulativos |

---

## Output Format

String com nome do próximo node: `"simular_regime_regular"` ou `"simular_regime_hibrido_simples"`

---

## Input Variables

| Variável | Tipo | Origem |
|----------|------|--------|
| `regime_tributario` | str | `OperacaoFrete.regime_tributario` |
