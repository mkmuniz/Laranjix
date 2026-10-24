# Tipologias de fraude

Cada tipologia da v1 tem uma página própria nesta pasta, escrita **do ponto de
vista de quem detecta**: qual é a assinatura no grafo e por que ela aparece.
Nenhuma página descreve como executar um golpe.

Toda tipologia precisa citar a **fonte pública** que a fundamenta.

| # | Tipologia | Assinatura no grafo | Estado |
|---|-----------|---------------------|--------|
| T1 | Cadeia de contas laranja (Pix) | Caminhos direcionados de 2 a 6+ saltos, intervalos curtos, saldo que não permanece nas contas intermediárias | ✅ [`t1_mule_chain.py`](../../src/laranjix/typologies/t1_mule_chain.py) |
| T2 | Golpes de engenharia social | Fan-in de vítimas sem relação prévia em janela curta, seguido de fan-out rápido | ✅ [`t2_social_engineering.py`](../../src/laranjix/typologies/t2_social_engineering.py) |
| T3 | Pulverização e smurfing | Muitas transações de valores próximos, logo abaixo de limiares, concentradas no tempo | ⬜ Marco 5 |
| T4 | Empresas de fachada | Subgrafo de PJs ligadas por sócios em comum, com fluxo intenso logo após a abertura | ⬜ Marco 6 |
| T5 | Lavagem em ciclo (layering) | Ciclos direcionados, disfarçados com valores variáveis e atrasos | ⬜ Marco 5 |
| T6 | Fraude de boleto | Pagamento para beneficiário sem relação histórica, recebedor com fan-in de pagadores diversos | ⬜ Marco 6 |

## As duas que existem

Uma tipologia é um plugin em `src/laranjix/typologies/`, com a interface de
[`base.py`](../../src/laranjix/typologies/base.py). Ela recebe a movimentação
normal que já existe e planta casos dentro dela, devolvendo as transações que
acrescentou e, **em separado**, o gabarito.

As assinaturas não são afirmadas na documentação: são verificadas em
[`tests/test_dataset.py`](../../tests/test_dataset.py).

| Verificação | O que o teste exige |
|---|---|
| T1 é um caminho direcionado | Cada salto parte de onde o anterior chegou |
| T1 não ganha valor | O valor nunca sobe de um salto para o próximo |
| T2 é fan-in | ≥ 3 pagadores distintos, todos para a mesma conta |
| T2 é seguido de fan-out | A saída começa depois da primeira entrada |
| Nenhuma isca vira fraude | As contas legítimas de *pass-through* ficam fora do gabarito |

O quanto elas ficam escondidas é controlado pelos níveis `easy`, `medium` e
`hard` — mulas com histórico prévio, valores tirados do histórico da vítima,
intervalos mais largos e falsos positivos legítimos plantados. Os resultados
medidos estão em [benchmark.md](../benchmark.md).

### Base já existente para T4

A tabela `company_partners` cria as arestas de sociedade entre PF e PJ, e
`laranjix.population.partners.shared_partner_pairs` identifica pares de empresas
que compartilham sócio.

## Fontes que fundamentam as tipologias

- **Carta Circular BCB nº 4.001/2020** (e alterações) — lista oficial de situações
  que podem indicar lavagem de dinheiro. Principal fonte das tipologias.
- **Resolução BCB nº 493/2025** (MED 2.0) — rastreamento e bloqueio em cadeia em
  até cinco camadas; parametriza a profundidade das cadeias de T1.
- **Resolução BCB nº 142/2021** — limite noturno do Pix; base de T3.
- **COAF — coletâneas "Casos & Casos"** (2016 e 2021) — casos brasileiros com
  fluxogramas do caminho do dinheiro; base de T4 e T5.
- **GAFI/FATF** — relatórios de tipologias internacionais.
- **Comunicados oficiais do BCB e de instituições sobre golpes do Pix** — base de T2.

A lista completa, com o uso de cada fonte, está na seção 6 do [ESCOPO.md](../../ESCOPO.md).
