<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/laranjix-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/laranjix-logo-light.svg">
    <img src="docs/assets/laranjix-logo-light.svg" alt="Laranjix — synthetic fraud graphs for Brazil" width="420">
  </picture>
</p>

<p align="center">
  <em>Gerador open source de datasets <strong>sintéticos</strong> de transações financeiras brasileiras,<br>
  com fraudes plantadas e rotuladas, para treinar e avaliar modelos de detecção de fraude.</em>
</p>

<p align="center">
  <a href="LICENSE"><img alt="Licença" src="https://img.shields.io/badge/licen%C3%A7a-Apache--2.0-blue.svg"></a>
  <a href="pyproject.toml"><img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg"></a>
  <a href="CHANGELOG.md"><img alt="Status" src="https://img.shields.io/badge/status-pre--alpha-orange.svg"></a>
</p>

**Nenhum dado real de pessoas, empresas ou instituições é usado em qualquer etapa do projeto.**
Os CPFs e CNPJs gerados têm dígitos verificadores **inválidos por construção**, os e-mails usam
apenas domínios reservados pela RFC 2606 e os telefones usam um DDD que não existe. Isso é
verificado automaticamente a cada commit — ver [docs/privacy.md](docs/privacy.md).

## O dataset funciona? A evidência

A pergunta que importa sobre um dataset sintético de fraude não é se ele parece
realista. É se um modelo treinado nele **aprende alguma coisa** — e se o problema que
ele propõe é difícil o bastante para valer a pena.

Ambas as coisas são medidas, não afirmadas. Reproduza com:

```bash
laranjix benchmark --accounts 20000 --seed 11 --runs 5
```

**2,34 milhões de transações · 0,09% de fraude · split temporal · 5 treinos por modelo**

| Dificuldade | Modelo | PR-AUC | Recall @ 1% FPR |
|---|---|---:|---:|
| **easy** | Regras simples | 0.2768 | 0.501 |
| | Tabular (sem grafo) | 0.1061 ± 0.0249 | 0.580 ± 0.033 |
| | **Tabular + grafo** | **0.4544 ± 0.1542** | **0.715 ± 0.116** |
| **medium** | Regras simples | 0.0075 | 0.050 |
| | Tabular (sem grafo) | 0.0277 ± 0.0056 | 0.288 ± 0.037 |
| | **Tabular + grafo** | **0.3032 ± 0.0416** | **0.589 ± 0.089** |
| **hard** | Regras simples | 0.0013 | 0.007 |
| | Tabular (sem grafo) | 0.0199 ± 0.0028 | 0.268 ± 0.020 |
| | **Tabular + grafo** | **0.2049 ± 0.0299** | **0.576 ± 0.036** |

Três coisas saem dessa tabela.

### 1. O nível `hard` é difícil de verdade

Regras escritas à mão despencam de **PR-AUC 0.2768 para 0.0013** entre `easy` e `hard`.
Com uma taxa base de 0,092%, isso é **1,4× o acaso** — na prática, inútil. O recall a
1% de falso positivo cai de 50% para 0,7%.

Esse é o critério de qualidade da seção 7.2 do [ESCOPO.md](ESCOPO.md): *se as regras
simples acertam quase tudo no nível `hard`, o dataset está fácil demais.* Não é uma
promessa no texto — é um [teste que quebra o build](tests/test_benchmark.py) se deixar
de valer.

### 2. A estrutura de grafo é onde está o sinal

O mesmo modelo, com os mesmos dados, mudando só as features:

| | Tabular | Tabular + grafo | Ganho |
|---|---:|---:|---:|
| easy | 0.1061 | 0.4544 | **4,3×** |
| medium | 0.0277 | 0.3032 | **10,9×** |
| hard | 0.0199 | 0.2049 | **10,3×** |

As 10 features tabulares são o que qualquer modelo linha-a-linha vê: valor, hora, idade
da conta. As 10 de grafo só existem porque a transação é uma **aresta numa rede**:
quantos pagadores distintos caíram nesse recebedor na última hora, se esse par já
transacionou antes, se o dinheiro entrou na conta do remetente minutos antes de sair.

É a tese do projeto, medida: no `hard`, um modelo tabular fica em 22× a taxa base e o
mesmo modelo com grafo chega a 223×.

### 3. Os números vêm com incerteza, porque precisam

Cada célula é a **média de 5 treinos** com sementes diferentes, com o desvio padrão ao
lado. Isso não é enfeite: com ~2.000 fraudes no período de teste, uma única semente
chegou a marcar PR-AUC 0.199 onde as vizinhas marcaram entre 0.47 e 0.63. Publicar
execução única seria publicar ruído.

### O que torna o `hard` difícil

Quatro mecanismos, todos configuráveis:

1. **Mulas com histórico.** 95% das contas laranja são contas comuns, com movimentação
   normal anterior. "Conta nova" deixa de ser sinal.
2. **Valores tirados do próprio histórico da vítima.** O valor da fraude é um valor que
   aquela vítima poderia ter enviado de qualquer forma.
3. **Falsos positivos plantados.** 220 contas legítimas fazem *pass-through* rápido —
   lojista pagando fornecedor, síndico repassando condomínio. "Entrou e saiu em uma
   hora" deixa de ser regra.
4. **Rótulo com atraso.** Ver abaixo.

### O rótulo não chega junto com a transação

No mundo real a fraude só é rotulada quando a vítima contesta — pelo MED, em até
**80 dias** (o prazo subiu de 30 para 80 em 1º de setembro de 2026). Um benchmark que
entrega o rótulo no instante da transação treina um modelo que não pode existir.

Por isso o gabarito tem uma coluna `label_available_at`, e o split temporal a respeita:
no treino, uma fraude ainda não contestada até a data de corte entra como transação
comum. No `hard`, foram **248 fraudes** treinadas como legítimas — exatamente a situação
de um time real.

Nenhum dos geradores de referência (AMLworld, AMLSim, SAML-D, PaySim) modela isso.

### Verificação do dataset

Além do benchmark, todo dataset gerado emite um relatório recalculável:

```bash
laranjix certify out/
```
```
Privacidade          nenhum documento valido e nenhum achado de PII
Reprodutibilidade    a seed 42 reproduziu 8 arquivo(s) byte a byte
Fidelidade           9 distribuicoes, pior caso 0.7x o ruido
```

Privacidade e reprodutibilidade são recalculadas do zero; a fidelidade compara cada
distribuição gerada com o alvo da calibração, usando como limiar o desvio que o próprio
tamanho da amostra produz. Esse teste já pagou por si: reprovou o mix de chaves Pix com
**18,6× o ruído**, um defeito real do gerador, [documentado e corrigido](docs/quality.md).

Metodologia completa em [docs/quality.md](docs/quality.md) e [docs/benchmark.md](docs/benchmark.md).

### O que ainda não está provado

- **TSTR contra base real.** O harness existe e está testado, mas o número depende de
  quem tem a base. A base real nunca entra no repositório; só a métrica sai.
- **Realismo dos parâmetros.** A fidelidade mede o gerador contra sua calibração, não
  contra o Brasil. Os parâmetros ainda são provisórios, e o relatório diz quais.
- **Comparação direta com AMLworld e SAML-D.** Planejada para o Marco 7.

## Por que existe

Os geradores públicos de dados de fraude (IBM AMLworld, AMLSim, SAML-D, PaySim) não modelam o
Brasil. O Laranjix modela o Pix como meio dominante, cadeias de contas laranja alinhadas ao
rastreamento do MED 2.0, golpes de engenharia social típicos do país, PF e PJ com empresas de
fachada e sócios em comum, e o calendário brasileiro.

E, principalmente, entrega fraudes **difíceis de detectar**: um dataset em que a fraude é óbvia
não serve nem para treinar nem para avaliar modelos.

Para quem: quem pesquisa detecção de fraude (em especial com GNNs), quem precisa de um benchmark
padronizado e quem quer testar ingestão e desempenho de bancos de grafo sem tocar em dado real.

## Estado atual

Pré-alfa. O que já funciona hoje:

| Marco | Entrega | Estado |
|-------|---------|--------|
| 0 | Repositório, licença, regras de contribuição, CI | ✅ |
| 2 | População: contas PF/PJ/MEI, chaves Pix, sociedades | ✅ |
| 3 | Movimentação normal em Pix, com calendário brasileiro | ✅ |
| 4 | Fraudes rotuladas T1 e T2, gabarito separado, benchmark | ✅ |
| — | Verificação do dataset (`laranjix certify`) | ✅ |
| 1 | Calibração com números derivados das fontes públicas | 🚧 parâmetros provisórios |
| 3 | TED, boleto e cartão de débito | ⬜ |
| 5 | T3 (pulverização) e T5 (lavagem em ciclo) | ⬜ |

O roadmap completo está em [ESCOPO.md](ESCOPO.md), seção 8.

> ⚠️ Os parâmetros de calibração atuais são **provisórios**: valores de ordem de grandeza
> plausível, transcritos manualmente para destravar o gerador. O comando `laranjix calibration`
> mostra quais ainda são provisórios. O Marco 1 os substitui por números derivados direto das
> APIs do BCB e do IBGE.

## Instalação

```bash
git clone git@github.com:mkmuniz/Laranjix.git
cd Laranjix
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso

Gerar uma população de 50 mil contas fictícias:

```bash
laranjix generate --accounts 20000 --seed 11 --difficulty hard --out out/
```

```
accounts                    20,000 linhas
pix_keys                    42,257 linhas
company_partners             2,737 linhas
institutions                    12 linhas
transactions             2,344,342 linhas
labels_transactions      2,344,342 linhas
labels_accounts              2,230 linhas
cases                          210 linhas
taxa de fraude            0.0917%  (dificuldade: hard)
o gabarito fica em arquivos separados (labels_*, cases) para evitar vazamento de rotulo
privacidade: nenhum achado.
```

Outros comandos:

```bash
laranjix benchmark            # treina os modelos de referência e mede o dataset
laranjix certify out/         # recalcula privacidade, reprodutibilidade e fidelidade
laranjix calibration          # fontes e estado de cada parâmetro
laranjix privacy-check out/   # varredura de PII em qualquer arquivo ou pasta
laranjix generate-population  # só a população, sem transações
laranjix generate --config exemplo.yaml
```

Configuração por arquivo:

```yaml
# exemplo.yaml
seed: 42
difficulty: hard
formats: [parquet, csv]
output_dir: out
population:
  accounts: 20000
  reference_date: 2026-01-01
fraud:
  mule_chain_cases: 120
  social_engineering_cases: 90
  chain_depth_max: 6
```

## Escala

Medido num MacBook (Apple Silicon), geração de ponta a ponta:

| Escala | Tempo | Pico de memória |
|--------|------:|----------------:|
| 200 mil contas (população) | 1,9 s | 0,6 GB |
| 1 milhão de contas (população) | 9,5 s | 1,4 GB |
| 20 mil contas → 2,3 M transações | 5,4 s | 1,4 GB |
| 60 mil contas → 7,0 M transações | 17,6 s | 3,2 GB |

Cerca de 105 mil contas/s e 400 mil transações/s, com custo **linear** no tamanho —
há um [teste que falha](tests/test_performance.py) se isso deixar de valer.

**O limite hoje é memória, não tempo.** O dataset inteiro é montado em memória antes de
ser escrito, a cerca de 460 bytes por transação. Passar de ~20 M de transações exige
geração em blocos com escrita por *row-group*, que ainda não existe.

## Reprodutibilidade

Mesma `seed` + mesma configuração = mesmo dataset, byte a byte. Cada geração escreve um
`manifest.json` com a versão do Laranjix, a configuração completa, a seed, o hash de cada
arquivo e o *fingerprint* dos parâmetros de calibração usados.

Cada etapa do pipeline sorteia de um fluxo próprio, derivado da seed e do nome da etapa. Assim,
acrescentar uma etapa nova não desloca os números sorteados pelas etapas existentes.

## Modelo de dados

Hoje o gerador produz quatro tabelas, em Parquet e CSV:

**Dados** — o que um modelo pode ver:

| Tabela | Conteúdo |
|--------|----------|
| `accounts` | Contas PF/PJ/MEI com documento fictício, UF, instituição, data de abertura, faixa de renda e perfil de uso |
| `pix_keys` | Chaves Pix (`cpf`, `cnpj`, `email`, `phone`, `evp`) com data de cadastro |
| `company_partners` | Arestas de sociedade entre PF e PJ — base da tipologia de empresas de fachada |
| `institutions` | Instituições fictícias (`inst_01`…), nunca um banco ou ISPB real |
| `transactions` | Pix com valor, horário, janela noturna e dispositivo |

**Gabarito** — em arquivos separados, para não vazar rótulo no treino:

| Tabela | Conteúdo |
|--------|----------|
| `labels_transactions` | `is_fraud`, tipologia, caso, papel e **`label_available_at`** |
| `labels_accounts` | Quais contas participaram e em que papel |
| `cases` | Um caso por linha: tipologia, dificuldade, profundidade, valor, fonte pública |

O esquema completo, incluindo transações e gabarito, está em [ESCOPO.md](ESCOPO.md), seção 3.

## Uso responsável

As tipologias de fraude se limitam ao que já é público em normas e publicações oficiais (Carta
Circular BCB 4.001, coletâneas do COAF, relatórios do GAFI/FATF), e são documentadas do ponto de
vista de **quem detecta**. O projeto não inclui, e não aceita, funcionalidades para otimizar
fraudes contra detectores específicos nem documentação operacional de como executar golpes.

Resultados obtidos em datasets do Laranjix **não demonstram desempenho em produção**.

## Contribuindo

Leia [CONTRIBUTING.md](CONTRIBUTING.md). A regra número um: nenhum dado real, nunca — nem
anonimizado, nem o seu próprio.

## Licença

Código sob [Apache-2.0](LICENSE). Os parâmetros de calibração derivados de dados abertos do
Banco Central estão sujeitos à ODbL; ver [NOTICE](NOTICE).

A identidade visual em `docs/assets/` é distribuída sob a mesma licença do projeto.
