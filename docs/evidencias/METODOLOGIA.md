# Metodologia — `tabela_transicao_local.json`

Este documento explica como os números da tabela foram construídos, para que você consiga
justificar as escolhas no README.md e no vídeo de demonstração (item "Automação" /
"Fundamentação técnica").

## 1. O que é oficial vs. estimado

A tabela separa dois tipos de dado:

- **`oficial: true`** — valor definido diretamente em artigo de lei (LC 214/2025) ou publicado
  pela Receita Federal como cronograma oficial. Exemplo: as alíquotas-teste de 2026 (0,9% CBS
  + 0,1% IBS) e o cronograma de substituição percentual do ICMS/ISS em 2029-2032
  (10/20/30/40%).
- **`oficial: false`** (ou `oficial_valor_aliquota: false`) — valor **projetado** por órgãos
  técnicos (Ministério da Fazenda, Comitê Gestor do IBS) mas que ainda depende de resolução
  do Senado Federal, prevista para ocorrer até 2035 (art. 18 da LC 214/2025). Isso vale
  principalmente para a alíquota de referência da CBS (2027+) e a alíquota plena do IBS
  (2033).

**Por que isso importa para o projeto avaliativo:** o requisito de "segurança e governança"
pede que o agente não apresente como certeza algo que não é. A simulação deve deixar claro,
na resposta ao usuário, quando um número é projeção — isso é testável e demonstrável no
cenário de QA.

## 2. Como os valores de 2029-2032 foram calculados

Fórmula aplicada (fonte: cronograma oficial da Receita Federal):

```
aliquota_ibs_ano = percentual_substituicao_ano × aliquota_ibs_plena_estimada
aliquota_icms_ano = percentual_remanescente_ano × aliquota_icms_vigente_em_31_12_2028
```

Onde `percentual_substituicao` segue exatamente o cronograma oficial:

| Ano | IBS (% da plena) | ICMS/ISS (% da base 2028) |
|---|---|---|
| 2029 | 10% | 90% |
| 2030 | 20% | 80% |
| 2031 | 30% | 70% |
| 2032 | 40% | 60% |
| 2033 | 100% | 0% (extinto) |

A `aliquota_ibs_plena_estimada` (19,1%) foi obtida por diferença: projeção do CGIBS de
alíquota combinada de referência (27,91%) menos a CBS (8,8%). **Essa subtração é uma
simplificação didática nossa** — na prática, IBS e CBS têm bases de cálculo e critérios de
fixação diferentes (arts. 353-359 para CBS, 361-366 para IBS), então o valor real pode
divergir. Documentar essa limitação no README é parte do requisito de "análise crítica e
limitações".

## 3. Baseline do regime atual

Usamos como comparação:
- PIS (1,65%) + COFINS (7,6%) — regime não cumulativo, Lucro Real
- ICMS médio interestadual (~12%) — este é o número mais frágil da simulação, porque o ICMS
  varia por par de UF (pode ir de ~7% a ~18%). Se quiser aumentar a precisão do projeto,
  vale substituir esse valor fixo por uma tabela de alíquotas interestaduais de ICMS por UF
  de origem/destino (dado público, ex. CONFAZ).

## 4. Como manter atualizado

1. Verificar periodicamente `https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm`
   (texto consolidado) e o portal `gov.br/receitafederal` (seção Reforma do Consumo).
2. Se o Senado publicar resolução fixando a alíquota de referência definitiva, atualizar os
   campos `oficial_valor_aliquota` para `true` e registrar a mudança em
   `docs/evidencias/ciclo-refinamento.md` (o próprio ato de atualizar a tabela pode virar o
   "ciclo de refinamento" documentado no Requisito 10).
3. Versionar sempre com um novo valor em `_metadata.versao` (`v2`, `v3`...) para rastrear
   qual tabela foi usada em cada simulação — isso é o que preenche o campo `fonte_tool` do
   `ResultadoAno` no design.

## 5. Fontes consultadas para montar esta tabela

- LC 214/2025, arts. 343, 344, 346, 347, 348 — planalto.gov.br
- Receita Federal — cronograma oficial da Reforma Tributária do Consumo
- ConJur — período de testes do IBS e CBS (30/dez/2025)
- Contábeis — alíquota de referência da CBS projetada em 8,8%–9,43% para 2027
- Contábeis — CGIBS estima alíquota de referência de 27,91% (acima do teto de 26,5%)
- Simtax — didática da transição ICMS→IBS 2029-2032 com exemplo numérico
- Fretebras / Edenred / Planning — impacto específico no transporte de cargas (frete)
