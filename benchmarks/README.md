# Benchmark

Ainda não implementado. Entra no Marco 7 (v0.4), depois que as tipologias e os
níveis de dificuldade existirem.

O que o marco entrega, conforme a seção 7 do [ESCOPO.md](../ESCOPO.md):

- splits de treino, validação e teste **temporais** (o teste é o "futuro");
- baselines de referência: regras simples, XGBoost com features de grafo e uma GNN simples;
- métricas: precisão, recall, F1, PR-AUC e recall com taxa de falso positivo fixa.

**Critério de qualidade:** se as regras simples acertam quase tudo no nível
`hard`, o dataset está fácil demais e a tipologia precisa ser revista.
