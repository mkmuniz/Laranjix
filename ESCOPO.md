# Laranjix — Documento de Escopo

> Gerador open source de datasets sintéticos de transações financeiras brasileiras, com fraudes plantadas e rotuladas, para treinar e avaliar modelos de detecção de fraude.

**Status:** rascunho v0.2 · **Licença pretendida:** Apache-2.0 · **Idioma do projeto:** português (docs) + inglês (código e API)

---

## 1. Objetivo

Criar datasets **sintéticos, rotulados e realistas** do sistema financeiro brasileiro que permitam:

1. **Treinar** modelos de detecção de fraude, com foco em redes neurais de grafo (GNNs), mas também modelos tabulares (XGBoost, regressão logística etc.).
2. **Avaliar e comparar** modelos de forma padronizada (benchmark), com níveis de dificuldade conhecidos.
3. **Testar infraestrutura**: ingestão e desempenho de bancos de grafo e pipelines de dados.

Tudo isso **sem usar nenhum dado real** de pessoas, empresas ou instituições.

### O que diferencia o Laranjix

Os geradores existentes (IBM AMLworld, AMLSim, SAML-D, PaySim, SantanderAI/gen-fraud-graph) não modelam o Brasil. O Laranjix modela:

- o **Pix** como meio de pagamento dominante, com chaves, limites noturnos e velocidade de repasse;
- **cadeias de contas laranja** em várias camadas, alinhadas ao rastreamento do MED 2.0;
- **golpes de engenharia social** típicos do país;
- **PF e PJ** com CPF/CNPJ (fictícios e inválidos por construção), empresas de fachada e sócios em comum;
- **calendário brasileiro**: salários, benefícios, feriados, horários.

E, principalmente, entrega fraudes **difíceis de detectar**. Um dataset em que a fraude é óbvia (valor fixo, descrição suspeita) não serve para treinar nem para avaliar modelos.

---

## 2. Escopo

### 2.1 Dentro do escopo (v1)

**O gerador produz:**

1. Uma rede de **contas** PF e PJ, com perfil socioeconômico, UF, idade da conta e instituição (fictícia).
2. **Transações normais** realistas nos meios Pix, TED, boleto e cartão de débito.
3. **Fraudes plantadas e rotuladas**, misturadas às transações normais.
4. **Ruído e camuflagem**: contas legítimas com comportamento que parece suspeito (falsos positivos realistas) e fraudes com valores e horários parecidos com os normais.
5. **Gabarito (ground truth)**: para cada transação e conta, se faz parte de um esquema, de qual tipologia, qual papel (vítima, laranja de 1ª camada, laranja de n-ésima camada, conta de saque, fachada etc.) e qual caso.
6. **Exportação** em Parquet e CSV, e adaptadores para PyTorch Geometric, DGL e Neo4j.
7. **Relatório de validação** que compara as distribuições geradas com estatísticas públicas do Banco Central.

### 2.2 Tipologias de fraude da v1

Cada tipologia tem uma "assinatura" no grafo, que é o que o modelo deve aprender a reconhecer.

| # | Tipologia | Descrição | Assinatura no grafo |
|---|-----------|-----------|---------------------|
| T1 | **Cadeia de contas laranja (Pix)** | Dinheiro da vítima passa por várias camadas de contas em minutos até uma conta de saque. | Caminhos direcionados com 2 a 6+ saltos, intervalos curtos, saldo que não permanece nas contas intermediárias. Configurável para testar o limite de 5 camadas do MED 2.0. |
| T2 | **Golpes de engenharia social** | Falsa central, golpe do WhatsApp, falso sequestro, golpe da devolução. | Fan-in: várias vítimas sem relação prévia enviando para a mesma conta em janela curta, seguido de fan-out rápido. Primeira transação entre as partes. |
| T3 | **Pulverização e smurfing** | Valores fracionados para ficar abaixo de limites de monitoramento e do limite noturno do Pix. | Muitas transações de valores próximos entre si e logo abaixo de limiares, concentradas no tempo. |
| T4 | **Empresas de fachada** | CNPJs recém-abertos, sócios em comum, faturamento incompatível com o porte. | Subgrafo de PJs ligadas por sócios (arestas de sociedade), com fluxos circulares ou fluxo intenso logo após a abertura. |
| T5 | **Lavagem em ciclo (layering)** | Dinheiro circula entre contas e volta à origem. | Ciclos direcionados, disfarçados com valores variáveis, atrasos e transações legítimas intercaladas. |
| T6 | **Fraude de boleto** | Boleto falso ou adulterado desvia o pagamento para conta de terceiro. | Pagamento de boleto para beneficiário sem relação histórica com o pagador, recebedor com fan-in de vários pagadores de "empresas" diferentes. |

Cada tipologia deve ser **documentada com a fonte pública** que a fundamenta (seção 6).

### 2.3 Níveis de dificuldade

| Nível | Características |
|-------|-----------------|
| `easy` | Fraudes com sinais claros; útil para testar o pipeline. |
| `medium` | Valores e horários parcialmente sobrepostos aos normais; algum ruído. |
| `hard` | Sobreposição forte, falsos positivos realistas, laranjas com histórico de uso "normal" antes de serem ativadas, proporção de fraude realista (baixa). |

Parâmetros ajustáveis: proporção de fraude, número de casos por tipologia, profundidade das cadeias, nível de camuflagem, escala.

### 2.4 Fora do escopo (v1)

- Treinar, distribuir ou manter modelos de detecção prontos (o projeto fornece apenas baselines de referência para o benchmark).
- Detecção em tempo real ou integração com sistemas de produção.
- Qualquer uso, ingestão ou armazenamento de dados reais de pessoas, empresas ou instituições.
- Outros domínios (saúde, seguros, licitações, e-commerce). O motor deve ser genérico o bastante para que isso venha depois como extensão.
- Guias de "como burlar sistemas antifraude" ou otimização de fraudes contra detectores reais (ver seção 5.6).

---

## 3. Modelo de dados

### 3.1 Entidades (nós)

**`accounts`**

| Campo | Tipo | Observação |
|-------|------|------------|
| `account_id` | string | Identificador interno (`acc_000001`). |
| `holder_type` | enum | `PF`, `PJ`, `MEI`. |
| `holder_id` | string | CPF/CNPJ **sintético e inválido por construção** (seção 5.2). |
| `holder_name` | string | Nome combinatório gerado (seção 5.2). |
| `institution_id` | string | Instituição fictícia (`inst_07`), nunca um ISPB real. |
| `uf` | string | Unidade federativa (distribuição calibrada por dados públicos). |
| `created_at` | datetime | Data de abertura da conta. |
| `income_band` | enum | Faixa de renda/faturamento. |
| `segment` | enum | Perfil de uso (assalariado, autônomo, varejo, serviço etc.). |

**`pix_keys`**

| Campo | Tipo | Observação |
|-------|------|------------|
| `key_id` | string | Identificador interno. |
| `account_id` | string | Conta vinculada. |
| `key_type` | enum | `cpf`, `cnpj`, `email`, `phone`, `evp` (aleatória). |
| `key_value` | string | Sempre fictício (seção 5.2). |
| `registered_at` | datetime | Chaves recém-cadastradas são sinal relevante. |

**`company_partners`** (arestas de sociedade entre PF e PJ)

| Campo | Tipo |
|-------|------|
| `partner_account_id` | string |
| `company_account_id` | string |
| `since` | datetime |

### 3.2 Transações (arestas)

**`transactions`**

| Campo | Tipo | Observação |
|-------|------|------------|
| `tx_id` | string | |
| `src_account_id` | string | |
| `dst_account_id` | string | |
| `channel` | enum | `pix`, `ted`, `boleto`, `debit_card`. |
| `pix_key_type` | enum | Tipo de chave usada (quando Pix). |
| `amount` | decimal | Em reais, com centavos. |
| `timestamp` | datetime | Fuso de Brasília. |
| `is_night` | bool | Janela 20h–6h. |
| `device_id` | string | Dispositivo fictício (troca de dispositivo é sinal). |
| `description` | string | Opcional; texto sintético e neutro (sem "palavras de fraude" plantadas). |

### 3.3 Gabarito

**`labels_transactions`**: `tx_id`, `is_fraud`, `typology`, `case_id`, `role`.

**`labels_accounts`**: `account_id`, `is_involved`, `roles` (lista), `case_ids`.

**`cases`**: `case_id`, `typology`, `difficulty`, `accounts`, `start_ts`, `end_ts`, `depth`, `total_amount`, `source_reference` (qual fonte pública fundamenta a tipologia).

O gabarito fica **em arquivos separados** dos dados, para evitar vazamento de rótulo no treino.

---

## 4. Arquitetura e stack

### 4.1 Linguagem

**Python 3.11+.** Motivos: é a linguagem do ecossistema de ML e GNN (PyTorch Geometric, DGL), facilita contribuições da comunidade de dados e permite publicar no PyPI.

Se a geração em escala muito grande (centenas de milhões de transações) virar gargalo, o núcleo de geração pode ganhar um módulo em Rust (via PyO3) mais adiante, mantendo a API em Python.

### 4.2 Bibliotecas principais

| Função | Biblioteca |
|--------|------------|
| Geração numérica | NumPy (com `Generator` e seed determinística) |
| Tabelas | Polars (principal) e Pandas (compatibilidade) |
| Escrita | PyArrow (Parquet) |
| Configuração | Pydantic + YAML |
| CLI | Typer |
| Validação de grafos | NetworkX (checagens em amostras) |
| Calendário | `holidays` (feriados brasileiros) |
| Adaptadores opcionais | `torch_geometric`, `dgl`, driver Neo4j |
| Qualidade | pytest, ruff, mypy, pre-commit |

### 4.3 Pipeline de geração

```
1. Calibração     → carrega parâmetros agregados de fontes públicas (arquivo versionado)
2. População      → cria contas PF/PJ, chaves Pix, sociedades
3. Comportamento  → gera transações normais (rotinas, sazonalidade, calendário)
4. Injeção        → planta casos de cada tipologia
5. Camuflagem     → adiciona ruído, falsos positivos e sobreposição
6. Rotulagem      → gera o gabarito separado
7. Exportação     → Parquet/CSV + adaptadores
8. Validação      → checagens de privacidade + relatório de realismo
```

Cada tipologia é um **plugin** (`laranjix/typologies/<nome>.py`) com interface comum, para que a comunidade possa contribuir com novas tipologias sem mexer no núcleo.

### 4.4 Reprodutibilidade

- Toda geração recebe uma `seed`. Mesma seed + mesma config = mesmo dataset, byte a byte.
- Cada dataset sai com um `manifest.json`: versão do Laranjix, config completa, seed, hash dos arquivos e versão dos parâmetros de calibração.

### 4.5 Estrutura do repositório

```
laranjix/
├── src/laranjix/
│   ├── cli.py
│   ├── config.py
│   ├── calibration/        # parâmetros agregados + scripts que os derivam
│   ├── population/         # contas, chaves, sociedades
│   ├── behavior/           # transações normais
│   ├── typologies/         # uma tipologia por arquivo (plugins)
│   ├── camouflage/         # ruído e falsos positivos
│   ├── privacy/            # geradores de identificadores seguros + checagens
│   ├── exporters/          # parquet, csv, pyg, dgl, neo4j
│   └── validation/         # relatório de realismo
├── benchmarks/             # baselines e scripts de avaliação
├── docs/
│   ├── typologies/         # uma página por tipologia, com fontes
│   └── privacy.md
├── tests/
└── .github/workflows/      # CI, checagem de PII, CodeQL, dependabot
```

---

## 5. Segurança e privacidade de dados

**Princípio central:** nenhum dado pessoal real entra no projeto, em nenhuma etapa: nem no código, nem nos parâmetros, nem nos datasets gerados, nem em contribuições.

### 5.1 Camada 1 — Calibração só com dados agregados

- O gerador só é calibrado com **estatísticas agregadas e públicas** (totais mensais, distribuições por município, contagens de fraude via MED). Nunca com microdados de indivíduos.
- É proibido usar vazamentos de dados, bases compradas, dados raspados de redes sociais ou dados de clientes de qualquer empresa, mesmo "anonimizados".
- Os parâmetros de calibração ficam num arquivo versionado e revisável, com a fonte de cada número.

### 5.2 Camada 2 — Identificadores impossíveis de coincidir com pessoas reais

| Dado | Estratégia |
|------|------------|
| **CPF** | Gerado com **dígitos verificadores deliberadamente inválidos**. Nenhum CPF gerado passa na validação oficial, logo não pode pertencer a ninguém. |
| **CNPJ** | Mesma estratégia: dígitos verificadores inválidos por construção. |
| **Nomes** | Combinação aleatória de prenomes e sobrenomes comuns. Um nome isolado pode coincidir com o de alguém, mas nunca vem associado a um documento válido, endereço ou dado real. |
| **E-mail** | Apenas domínios reservados para exemplos (`example.com`, `example.org`, conforme RFC 2606). |
| **Telefone** | Formato fictício sinalizado (padrão a definir, que não corresponda a numeração válida). |
| **Chave aleatória (EVP)** | UUID gerado localmente. |
| **Instituições** | Fictícias (`inst_01`...). Nenhum nome, código de banco ou ISPB real. |
| **Endereços** | Não gerados na v1. Apenas UF (e, no máximo, município em nível agregado). |

### 5.3 Camada 3 — Checagens automáticas no CI

Todo PR e toda geração de release passam por:

1. **Validador de documentos:** falha se qualquer CPF ou CNPJ gerado for válido pelo algoritmo oficial.
2. **Scanner de PII:** procura padrões de e-mail fora dos domínios permitidos, números de cartão (Luhn válido), telefones em formato real etc.
3. **Checagem de arquivos:** bloqueia a adição de arquivos de dados brutos (CSV, Parquet, XLSX) fora das pastas permitidas, para evitar que alguém suba dados reais por engano.
4. **CodeQL e dependabot** para segurança do código e das dependências.

### 5.4 Camada 4 — Governança de contribuições

- O `CONTRIBUTING.md` proíbe explicitamente submeter dados reais, mesmo que anonimizados.
- Novas tipologias precisam citar **fonte pública**; não aceitamos tipologias baseadas em casos internos de empresas ou em dados que o contribuidor não possa compartilhar publicamente.
- Revisão obrigatória por mantenedor (CODEOWNERS) para qualquer mudança em `privacy/` e `calibration/`.

### 5.5 Camada 5 — Transparência no dataset

Cada dataset publicado vem com um **dataset card** declarando: que é 100% sintético, a versão e seed, as fontes de calibração, as limitações conhecidas e que resultados obtidos nele **não demonstram desempenho em produção**.

### 5.6 Uso responsável (dual use)

Um gerador de fraudes descreve padrões de fraude. Para manter o projeto do lado certo:

- As tipologias se limitam ao que **já é público** em normas e publicações oficiais (Carta Circular 4.001, COAF, BCB).
- O projeto **não** inclui funcionalidades para otimizar fraudes contra detectores específicos, nem documentação operacional de como executar golpes.
- A documentação de cada tipologia descreve o padrão do ponto de vista de **quem detecta**.

### 5.7 LGPD

Como o projeto não coleta nem trata dados pessoais reais, a LGPD (Lei nº 13.709/2018) não incide sobre os datasets gerados. As camadas acima existem justamente para garantir que isso continue verdadeiro. Recomenda-se revisão jurídica antes da primeira release pública.

---

## 6. Fontes para fundamentar o gerador

### 6.1 Normas e regulação (fundamentam as regras e as tipologias)

| Fonte | Uso no Laranjix |
|-------|-----------------|
| **Resolução BCB nº 1/2020** (Regulamento do Pix) | Regras gerais do arranjo Pix; base do modelo de chaves e transações. |
| **Resolução BCB nº 142/2021** e normas complementares | Limite noturno de R$ 1.000 entre pessoas físicas (incluindo MEIs) das 20h às 6h, prazos para aumento de limite e cadastro de contas autorizadas. Usado em T3 (smurfing) e no comportamento normal. |
| **Resolução BCB nº 493/2025** (MED 2.0) | Rastreamento e bloqueio em cadeia em até cinco camadas de contas. Parametriza a profundidade das cadeias da T1. |
| **Circular BCB nº 3.978/2020** | Política de prevenção à lavagem de dinheiro das instituições; contexto de KYC/KYB. |
| **Carta Circular BCB nº 4.001/2020** (e alterações, como a IN BCB nº 461/2024) | Lista oficial de situações que podem indicar lavagem de dinheiro e devem ser comunicadas ao COAF. **Principal fonte das tipologias**: fragmentação de operações, movimentação incompatível com a capacidade financeira, sócios sem capacidade financeira para o porte da empresa, entre outras. |
| **Resolução Conjunta nº 6/2023** | Compartilhamento de dados sobre indícios de fraude entre instituições; contexto para sinais de "conta já reportada". |
| **Lei nº 9.613/1998** | Lei de lavagem de dinheiro; definições e fases. |
| **Lei nº 13.709/2018** (LGPD) | Diretrizes de privacidade (seção 5). |

### 6.2 Estatísticas públicas (calibram o realismo)

| Fonte | Uso no Laranjix |
|-------|-----------------|
| **BCB — Portal de Dados Abertos, conjunto "Estatísticas do Pix"** (API OData em `olinda.bcb.gov.br`, recursos `EstatisticasTransacoesPix`, `TransacoesPixPorMunicipio`, `ChavesPix` e `EstatisticasFraudesPix`) | Quantidade e volume mensal de transações, distribuição por município e PF/PJ, estoque de chaves por tipo e **estatísticas de fraude registradas no MED**. É a fonte mais importante para calibrar volume e proporção de fraude. Licença ODbL (ver 6.5). |
| **BCB — declarações oficiais sobre o Pix** | Ex.: na criação do limite noturno, o BC informou que 90% das transações noturnas eram de até R$ 500, o que ajuda a calibrar valores por horário. |
| **IBGE** (população por UF, faixas de renda) | Distribuição geográfica e socioeconômica das contas PF. |
| **Receita Federal — Dados Abertos do CNPJ** | **Somente estatísticas agregadas** (distribuição por porte, atividade, idade das empresas, número de sócios). Os registros individuais nunca entram no projeto. |
| **Anuário Brasileiro de Segurança Pública (FBSP)** e publicações da **Febraban** | Tendências e peso relativo de tipos de golpe (fontes secundárias, para priorizar tipologias). |

### 6.3 Casos e tipologias documentadas (fundamentam os padrões de fraude)

| Fonte | Uso no Laranjix |
|-------|-----------------|
| **COAF — "Casos & Casos: Coletânea Completa de Casos Brasileiros de Lavagem de Dinheiro"** (2016) | Casos reais descritos com fluxogramas do caminho do dinheiro, agrupados por crime antecedente. Base para T4 e T5. |
| **COAF — "Casos & Casos: Tipologias — Edição Especial Avaliação Nacional de Riscos" (2021)** | Tipologias mais recentes do contexto brasileiro. |
| **COAF / Grupo de Egmont — "Cem casos de lavagem de dinheiro"** | Casos internacionais de referência. |
| **GAFI/FATF** — relatórios de tipologias | Padrões internacionais (mulas, TBML, uso de empresas de fachada). |
| **Comunicados do BCB e das instituições sobre golpes do Pix** | Descrições públicas de falsa central, golpe do WhatsApp, golpe da devolução etc. Base para T2. |

> Nota: não existe base pública de "transações comprovadamente fraudulentas" do sistema brasileiro em nível de transação, e isso é esperado por sigilo bancário e LGPD. O que existe publicamente são **estatísticas agregadas** (como o MED no portal do BCB) e **casos descritos** (COAF). O Laranjix combina as duas coisas: as estatísticas definem *quanto* e *quando*; os casos definem *como*.

### 6.4 Datasets e geradores de referência (benchmark e inspiração)

| Projeto | Tipo | Uso no Laranjix |
|---------|------|-----------------|
| **IBM AMLworld** (NeurIPS 2023; datasets públicos no Kaggle) | Sintético, simulação por agentes, 8 padrões de lavagem | Referência de arquitetura e de realismo; comparação de dificuldade dos benchmarks. |
| **IBM AMLSim** (GitHub) | Sintético, simulação por agentes | Referência de configuração e schema aberto. |
| **SAML-D** (Bournemouth University) | Sintético, 28 tipologias | Referência de variedade de tipologias. |
| **PaySim** | Sintético, pagamentos móveis | Pagamentos instantâneos no celular, análogo ao Pix. |
| **BankSim** | Sintético, pagamentos com cartão | Modelagem de comportamento de clientes e comerciantes. |
| **Sparkov** (Credit Card Transactions, Kaggle) | Sintético, cartão de crédito | Comportamento de cartão ao longo do tempo. |
| **SantanderAI/gen-fraud-graph** | Sintético, anéis de fraude em grafo | Referência de código: CLI, escala, paralelismo, exportação para bancos de grafo. |
| **IEEE-CIS Fraud Detection** (Kaggle) | Real e anonimizado, e-commerce | Referência de features e de proporção de fraude realista. **Não** é incorporado aos dados. |
| **Credit Card Fraud (ULB, Kaggle)** | Real e transformado (PCA) | Referência de desbalanceamento extremo de classes. **Não** é incorporado. |
| **Elliptic Dataset** | Real, transações Bitcoin rotuladas | Referência de benchmark de GNN em grafo de transações. **Não** é incorporado. |

**Regra:** datasets reais (mesmo anonimizados) servem apenas como **referência de comparação estatística e de metodologia**. Nenhum registro deles é copiado para os dados do Laranjix.

### 6.5 Licenças das fontes

- Os dados abertos do BCB usam a licença **ODbL**, que exige atribuição e tem cláusula de compartilhamento pelas mesmas condições para bases derivadas. Os parâmetros de calibração derivados do BCB devem ficar num arquivo separado, com atribuição, e a compatibilidade com a licença Apache-2.0 do código precisa ser confirmada antes da release.
- Verificar a licença de cada dataset da seção 6.4 antes de usá-lo em qualquer comparação publicada.

---

## 7. Validação e benchmark

### 7.1 Realismo

O relatório de validação compara o dataset gerado com as estatísticas públicas:

- volume e valor médio por canal e por mês;
- distribuição por UF e PF/PJ;
- distribuição horária (incluindo a janela noturna);
- proporção de fraude comparada ao MED;
- propriedades do grafo (distribuição de graus, componentes, reciprocidade).

### 7.2 Benchmark

Para cada nível de dificuldade, o projeto publica:

- splits de treino, validação e teste **temporais** (o teste é o "futuro");
- baselines de referência: regras simples, XGBoost com features de grafo e uma GNN simples;
- métricas: precisão, recall, F1, PR-AUC e recall com taxa de falso positivo fixa.

**Critério de qualidade:** se as regras simples acertam quase tudo no nível `hard`, o dataset está fácil demais e a tipologia precisa ser revista.

---

## 8. Roadmap e milestones

Cada marco termina com algo concreto que dá para mostrar. As tarefas estão em linguagem simples; o detalhamento técnico de cada uma fica nas issues do GitHub.

| Marco | Nome | Versão |
|-------|------|--------|
| 0 | Preparação | — |
| 1 | Pesquisa e fontes | — |
| 2 | Pessoas e contas fictícias | — |
| 3 | Movimentação normal | — |
| 4 | Primeiras fraudes | **v0.1** |
| 5 | Mais fraudes e níveis de dificuldade | **v0.2** |
| 6 | Empresas, boletos e integrações | **v0.3** |
| 7 | Benchmark | **v0.4** |
| 8 | Versão 1.0 e divulgação | **v1.0** |

### Marco 0 — Preparação
*Resultado: o projeto existe publicamente e tem regras claras.*

- [ ] Criar o repositório com o nome Laranjix e reservar o nome no PyPI.
- [ ] Escrever uma página inicial (README) explicando o que é o projeto e para quem ele serve.
- [ ] Escrever as regras de contribuição, deixando claro que é proibido enviar dados reais.
- [ ] Escolher a licença e confirmar se ela combina com a licença dos dados do Banco Central.
- [ ] Organizar as pastas do projeto conforme a seção 4.5.

### Marco 1 — Pesquisa e fontes
*Resultado: os números e os padrões de fraude estão reunidos e documentados.*

- [ ] Baixar as estatísticas do Pix do Banco Central (volume por mês, por cidade, fraudes do MED).
- [ ] Ler a lista oficial de situações suspeitas do Banco Central (Carta Circular 4.001) e anotar as que servem para o projeto.
- [ ] Ler as coletâneas de casos do COAF e resumir os padrões de fraude encontrados.
- [ ] Juntar esses números num único arquivo de "parâmetros", com a fonte de cada um.
- [ ] Escrever uma página para cada tipo de fraude, explicando como ele funciona e de onde veio a informação.

### Marco 2 — Pessoas e contas fictícias
*Resultado: o gerador cria uma população de clientes falsos, mas realistas.*

- [ ] Criar pessoas e empresas fictícias com nomes gerados.
- [ ] Criar CPFs e CNPJs que sejam impossíveis de pertencer a alguém real.
- [ ] Distribuir essas pessoas pelos estados de forma parecida com a população brasileira.
- [ ] Criar contas bancárias, com banco fictício e data de abertura.
- [ ] Criar chaves Pix para essas contas (CPF, e-mail, telefone, aleatória).
- [ ] Ligar sócios às suas empresas.

### Marco 3 — Movimentação normal
*Resultado: as contas fictícias movimentam dinheiro como clientes comuns.*

- [ ] Simular salários caindo no início do mês e contas sendo pagas.
- [ ] Simular compras, transferências entre amigos e pagamentos de boleto.
- [ ] Aplicar o calendário brasileiro: feriados, fins de semana, horários.
- [ ] Respeitar o limite noturno do Pix.
- [ ] Comparar o resultado com os números do Banco Central para ver se ficou parecido.

### Marco 4 — Primeiras fraudes (v0.1)
*Resultado: o gerador planta os dois golpes mais importantes e marca onde eles estão.*

- [ ] Criar cadeias de contas laranja, com o dinheiro passando por várias contas em minutos (T1).
- [ ] Criar golpes de engenharia social, com várias vítimas mandando dinheiro para a mesma conta (T2).
- [ ] Gerar o gabarito: um arquivo separado dizendo quais transações são fraude e qual o papel de cada conta.
- [ ] Salvar tudo em arquivos fáceis de abrir (CSV e Parquet).
- [ ] Criar as verificações automáticas de privacidade (nenhum CPF válido, nenhum e-mail real).
- [ ] Publicar a versão 0.1.

### Marco 5 — Mais fraudes e níveis de dificuldade (v0.2)
*Resultado: fraudes mais variadas e mais difíceis de achar.*

- [ ] Adicionar o fracionamento de valores, vários Pix pequenos para fugir de limites (T3).
- [ ] Adicionar a lavagem em ciclo, dinheiro dando a volta e retornando à origem (T5).
- [ ] Criar os níveis fácil, médio e difícil.
- [ ] Adicionar "ruído": clientes honestos que às vezes parecem suspeitos.
- [ ] Gerar um relatório automático comparando o dataset com os números oficiais.

### Marco 6 — Empresas, boletos e integrações (v0.3)
*Resultado: o dataset cobre empresas e funciona direto nas ferramentas de IA.*

- [ ] Adicionar empresas de fachada ligadas por sócios em comum (T4).
- [ ] Adicionar fraude de boleto (T6).
- [ ] Incluir TED e cartão de débito na movimentação.
- [ ] Permitir abrir os dados direto nas principais ferramentas de treino de IA de grafo e em bancos de grafo.

### Marco 7 — Benchmark (v0.4)
*Resultado: qualquer pessoa pode medir se o modelo dela é bom.*

- [ ] Separar os dados em treino e teste usando o tempo (o teste é o "futuro").
- [ ] Criar modelos simples de referência para comparação.
- [ ] Testar se o nível difícil é difícil de verdade; se não for, voltar e ajustar.
- [ ] Publicar os datasets prontos no Hugging Face ou Kaggle.

### Marco 8 — Versão 1.0 e divulgação (v1.0)
*Resultado: projeto estável e conhecido pela comunidade.*

- [ ] Revisar toda a documentação.
- [ ] Pedir a profissionais de prevenção à fraude que revisem os tipos de golpe.
- [ ] Publicar a versão 1.0 no PyPI.
- [ ] Pedir a inclusão na lista awesome-pix e escrever um artigo apresentando o projeto.

---

## 9. Governança open source

- **Licença:** Apache-2.0 (a confirmar compatibilidade com ODbL para os parâmetros de calibração).
- **Arquivos obrigatórios:** `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CODEOWNERS`, `CHANGELOG.md`.
- **Commits:** Conventional Commits.
- **Divulgação inicial:** lista `woovibr/awesome-pix`, comunidades de dados e segurança, artigo técnico explicando as tipologias.

---

## 10. Questões em aberto

1. Formato exato dos telefones fictícios (garantir que não correspondam a numeração válida).
2. Compatibilidade ODbL × Apache-2.0 para os parâmetros de calibração.
3. Onde hospedar os datasets de referência (Hugging Face, Kaggle ou ambos).
4. Buscar validação das tipologias com profissionais de prevenção à fraude.
5. Incluir ou não transações de cartão de crédito já na v1.
