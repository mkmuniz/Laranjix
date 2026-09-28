# Como o Laranjix mede a qualidade de um dataset

Um gerador de dados sintéticos precisa responder a uma pergunta desconfortável: *por que
alguém deveria acreditar nesses dados?* Este documento descreve os três níveis de
resposta que o projeto dá, e é explícito sobre o que cada um prova e o que não prova.

Tudo aqui é recalculável:

```bash
laranjix generate-population --accounts 50000 --seed 42 --out out/
laranjix certify out/
```

## Nível 1 — Privacidade: o dataset não pode conter dado de ninguém

Esse nível é garantido por construção, não por auditoria. Os detalhes estão em
[privacy.md](privacy.md); o certificado recalcula duas coisas:

1. **Todo documento é revalidado** pelo algoritmo oficial de CPF/CNPJ. O certificado
   reporta quantos foram checados e quantos passariam como válidos. O segundo número
   tem que ser zero.
2. **Todo arquivo é varrido** pelo scanner de PII, incluindo os Parquet, lidos como
   tabela.

## Nível 2 — Fidelidade: o gerador reproduz a calibração que recebeu?

Este é o nível mais fácil de fazer errado, porque comparar distribuições sem um limiar
honesto produz números sem significado.

### A métrica

**Distância de variação total (TVD)** entre a distribuição gerada e o alvo: a maior
diferença de probabilidade entre as duas, em `[0, 1]`. É interpretável — TVD de 0,05
quer dizer "no máximo 5 pontos percentuais de diferença em alguma categoria".

### O limiar

Nenhuma amostra finita reproduz exatamente a distribuição de onde foi sorteada. Sortear
50 mil contas de uma distribuição por UF *sempre* dá uma TVD maior que zero. Então
comparar a TVD com zero, ou com uma constante arbitrária como 0,01, não diz nada.

O limiar usado é o **desvio que o próprio tamanho da amostra produz**: sorteia-se 600
vezes da distribuição-alvo no tamanho real da amostra e toma-se o percentil 99,9 das
TVDs resultantes. Uma checagem falha só quando o desvio é maior do que o acaso explica.

O limiar encolhe com `1/√n`, como tem que ser:

| Amostra | Limiar de ruído (TVD) |
|---------|----------------------|
| 1.000 | 0,0488 |
| 10.000 | 0,0151 |
| 100.000 | 0,0052 |

Isso torna o teste **mais rigoroso quanto maior o dataset**, que é a propriedade certa:
num dataset grande, um desvio pequeno já é evidência de defeito.

### O que a seção 3 não prova

Ela compara o gerado com os **parâmetros de calibração**, não com o Brasil. Se um
parâmetro estiver errado, o dataset passa em tudo e continua irrealista. Por isso o
certificado lista, toda vez, quais parâmetros ainda são provisórios — hoje: `accounts`,
`pix_keys` e `population_uf`. Corrigir isso é o Marco 1.

### O primeiro defeito que o certificado pegou

Na primeira execução, duas checagens reprovaram:

| Distribuição | TVD | Limiar | × ruído |
|---|---:|---:|---:|
| Tipo de chave Pix (PF) | 0,11666 | 0,00629 | **18,6×** |
| Tipo de chave Pix (PJ) | 0,18289 | 0,01577 | **11,6×** |

EVP saía com 42,7% contra um alvo de 31% (PF) e 38,3% contra 20% (PJ).

**A causa.** Uma conta Pix tem no máximo uma chave de cada tipo de documento ou contato;
só a chave aleatória (EVP) repete. O gerador sorteava direto do alvo e, quando o tipo
sorteado já estava usado, **trocava por EVP**. Toda colisão caía no mesmo lugar.

**Por que a correção óbvia não resolve.** Re-sortear entre os tipos ainda permitidos,
renormalizando, corta o viés pela metade e só isso — TVD de 0,063 (PF) e 0,126 (PJ),
ainda dez vezes o ruído.

**A correção.** O alvo da calibração é um mix *realizado* — a participação de cada tipo
no estoque total de chaves, como o BCB publica. Sob a restrição de unicidade, esse alvo
não é a distribuição de onde se deve sortear. O gerador agora **resolve os pesos de
sorteio cujo resultado é o alvo**, iterando

```
w ← w · alvo / realizado(w)
```

onde `realizado(w)` é calculado **exatamente**, por programação dinâmica sobre quais
tipos únicos a conta já usou — sem Monte Carlo. Isso importa para a reprodutibilidade: a
solução depende só dos números da calibração, então é idêntica em qualquer máquina e
qualquer versão do NumPy.

Resultado: TVD residual de `1e-13`, e as duas checagens passaram a sair em 0,4× e 0,3×
o ruído. Implementação em [`population/key_mix.py`](../src/laranjix/population/key_mix.py).

## Nível 3 — Utilidade: o dataset treina um modelo que funciona no mundo real?

Fidelidade distribucional não responde isso. A resposta é o protocolo **TSTR**
(*train-on-synthetic, test-on-real*), padrão da literatura de dados sintéticos:

1. Treina-se um modelo **no dataset sintético**.
2. Avalia-se numa **base real** (TSTR).
3. Compara-se com o mesmo modelo **treinado na base real** (TRTR).
4. A razão **TSTR/TRTR** é o número de utilidade. `1,0` significa que o sintético treina
   tão bem quanto o real.

A métrica é **average precision** (área sob a curva precisão-recall), não ROC-AUC, que
é enganosamente alta em dados desbalanceados — e fraude é raríssima.

### A direção em que o dado corre

Este é o ponto que preserva a promessa do projeto:

> A base real fica na máquina de quem a possui, é passada em memória para a função de
> avaliação, e **nada dela é escrito** no dataset, no certificado ou no repositório.
> Só o número atravessa a fronteira.

Isso permite medir utilidade contra a realidade sem nunca importar um registro real.
É por isso que o Laranjix não transforma bases reais "anonimizadas": em dados
transacionais, [4 pontos espaço-temporais reidentificam 90% das
pessoas](https://www.science.org/doi/10.1126/science.1256297) — o que identifica não é o
CPF, é o padrão. A topologia do grafo de fraude que torna o dataset útil é exatamente a
impressão digital do caso real.

### Estado atual

**Pendente.** O TSTR precisa de rótulos de fraude, que chegam no Marco 4. O harness já
está implementado e testado (`laranjix.validation.tstr`), e o certificado reporta
`PENDENTE` em vez de inventar um número.

Para rodar quando houver rótulos:

```python
from laranjix.validation import run_tstr

resultado = run_tstr(
    synthetic_features,
    synthetic_labels,  # do dataset Laranjix
    real_features,
    real_labels,  # a sua base, que nao sai daqui
)
print(resultado.utility_ratio)
```

Instale com `pip install 'laranjix[bench]'` (traz o scikit-learn).

## Resumo do que cada nível prova

| Nível | Prova | Não prova |
|-------|-------|-----------|
| Privacidade | Nenhum dado pode ser de alguém real | — |
| Fidelidade | O gerador reproduz seus parâmetros | Que os parâmetros descrevem o Brasil |
| Utilidade (TSTR) | Um modelo treinado aqui funciona lá | Desempenho em produção |

E nenhum dos três substitui revisão jurídica antes de uma release pública.
