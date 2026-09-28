# Benchmark

O benchmark esta implementado em [`src/laranjix/benchmark/`](../src/laranjix/benchmark/)
e se roda pela CLI:

```bash
laranjix benchmark --accounts 20000 --seed 11 --runs 5
```

A metodologia esta em [docs/benchmark.md](../docs/benchmark.md) e os resultados atuais
no [README](../README.md#o-dataset-funciona-a-evidencia).

## O que ainda falta (Marco 7)

- GNN de referencia, alem do modelo tabular com features de grafo agregadas.
- Comparacao direta com AMLworld, AMLSim, SAML-D e PaySim.
- Publicacao dos datasets prontos no Hugging Face ou Kaggle.
