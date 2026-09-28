# O benchmark: como o dataset é medido

Este documento descreve o protocolo por trás da tabela do README, e é explícito sobre
as escolhas que costumam ser feitas errado.

```bash
laranjix benchmark --accounts 20000 --seed 11 --runs 5
```

## O protocolo

### Split temporal, e só temporal

Fraude evolui. Um split aleatório deixa o modelo ver o futuro do mesmo caso que está
prevendo — o mesmo `case_id` cai no treino e no teste, e o resultado fica inflado.

O corte é no percentil 70 do tempo. Treino é o passado, teste é o futuro.

### O rótulo chega atrasado

Esta é a parte que os geradores de referência não modelam.

No mundo real, uma transação fraudulenta não é rotulada quando acontece — ela é
rotulada quando a vítima contesta. Pelo MED, isso pode levar até **80 dias** (prazo
ampliado de 30 para 80 em 1º de setembro de 2026, Resolução BCB nº 493/2025).

O gabarito traz `label_available_at` separado de `timestamp`, com o atraso sorteado de
uma gama: a maioria das vítimas percebe em poucos dias, uma cauda longa leva semanas.

No treino, **só conta como fraude o que já tinha sido contestado até a data de corte**.
O resto entra como transação comum. No nível `hard`, isso são 248 fraudes treinadas
como legítimas — ruído de rótulo que um time real tem e um benchmark ingênuo esconde.

### A métrica é PR-AUC, não ROC-AUC

Com 0,09% de fraude, ROC-AUC fica alto para qualquer coisa e não distingue modelos.
A área sob a curva precisão-recall respeita o desbalanceamento.

A segunda métrica, **recall a 1% de falso positivo**, é a que um time de prevenção
realmente vive: o volume de alerta é limitado pelo número de analistas, então o que
importa é quanta fraude cabe dentro desse orçamento.

### Média sobre 5 treinos

Com cerca de 2.000 fraudes no período de teste, PR-AUC varia muito com a semente do
modelo. Medimos: uma semente marcou **0.199** onde as vizinhas marcaram entre 0.47 e
0.63. Toda célula da tabela é média de 5 sementes, com o desvio padrão ao lado.

Publicar execução única aqui seria publicar ruído.

## Os três modelos de referência

| Modelo | Features | Papel |
|--------|---------:|-------|
| Regras simples | 4 | O piso. Se elas resolvem o dataset, o dataset não presta. |
| Tabular (sem grafo) | 10 | Gradient boosting no que uma linha da tabela mostra. |
| Tabular + grafo | 20 | O mesmo modelo, com a transação vista como aresta. |

### As regras

Quatro bandeiras vermelhas que um analista escreve no primeiro dia, somadas:

1. Par inédito **e** valor ≥ R$ 1.000
2. Recebedor com ≥ 4 pagadores distintos na última hora
3. `passthrough_ratio` entre 0,80 e 1,05 **e** entrada há menos de 30 minutos
4. Conta de destino com menos de 30 dias **e** valor ≥ R$ 500

> **Nota honesta:** essas regras já usam sinais de velocidade e de rede — é o que
> motores de regra reais fazem. Elas não são um baseline "sem grafo". O baseline sem
> grafo é o modelo tabular, e é com ele que a coluna de grafo deve ser comparada.

### As features

**Tabulares (10):** valor em log, hora, janela noturna, dia da semana, idade das contas
de origem e destino, PF ou PJ de cada lado, valor em relação à mediana do remetente,
contagem de transações do remetente.

**De grafo (10):** quantas vezes esse par já transacionou, fan-in do recebedor na última
hora (contagem, pagadores distintos, valor), fan-out do remetente em 24h (contagem,
recebedores distintos), entrada na conta do remetente na última hora (contagem, valor),
razão de *pass-through*, segundos desde a última entrada.

A diferença entre os dois últimos modelos é o valor da topologia. Nada mais muda.

## O que os níveis de dificuldade mudam

| | easy | medium | hard |
|---|---:|---:|---:|
| Mulas com histórico prévio | 0% | 75% | 95% |
| Valor tirado do histórico da vítima | 0% | 80% | 95% |
| Intervalo entre saltos | 1–4 min | 3–75 min | 5–180 min |
| Falsos positivos plantados | 0 | 120 | 220 |

Esses valores **não são calibração**: nenhuma estatística pública diz quão óbvia uma
fraude deve parecer. São os controles que dão piso e teto ao benchmark.

O `medium` foi ajustado depois da primeira medição: com os valores iniciais ele marcava
o mesmo que o `easy` para o modelo de grafo, o que torna o degrau do meio inútil.

## O critério de aprovação

Da seção 7.2 do [ESCOPO.md](../ESCOPO.md):

> Se as regras simples acertam quase tudo no nível `hard`, o dataset está fácil demais
> e a tipologia precisa ser revista.

Isso é um teste, não uma intenção: `test_simple_rules_collapse_when_the_dataset_is_hard`
falha o build se as regras voltarem a passar de PR-AUC 0,05 no `hard`.

Resultado atual: **0.0013**, contra uma taxa base de 0,092% — 1,4× o acaso.

## Limitações conhecidas

- **Só T1 e T2.** T3 a T6 entram nos Marcos 5 e 6. A tabela mede o que existe.
- **Só Pix.** TED, boleto e cartão de débito ainda não são gerados.
- **Sem GNN de referência.** O modelo com grafo usa features agregadas, não aprendizado
  em grafo. Uma GNN deve ir melhor; medir isso é o Marco 7.
- **Sem comparação com AMLworld e SAML-D.** Planejada para o Marco 7.
- **O realismo dos parâmetros ainda não foi estabelecido.** Ver [quality.md](quality.md).
