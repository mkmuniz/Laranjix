# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- Estrutura do repositório, licença Apache-2.0 e regras de contribuição (Marco 0).
- Camada de privacidade: geradores de CPF/CNPJ inválidos por construção, nomes
  combinatórios, e-mails em domínios reservados (RFC 2606), telefones com DDD
  inexistente e chaves EVP locais.
- Validadores oficiais de CPF/CNPJ usados para *provar* que nenhum documento
  gerado é válido, e scanner de PII executado no CI.
- Parâmetros de calibração versionados com a fonte de cada número.
- Geração da população: contas PF/PJ/MEI, chaves Pix e arestas de sociedade (Marco 2).
- CLI `laranjix` com o comando `generate-population` e exportação em
  Parquet/CSV com `manifest.json` reprodutível.
- Identidade visual em `docs/assets/`: logo horizontal em variantes clara e
  escura e o símbolo isolado, usados no README.
- O scanner de PII passa a varrer arquivos `.svg`, mascarando os atributos de
  geometria para alcançar a metadata, que é onde um arquivo de design pode
  carregar nome e e-mail de quem o exportou.
- **Certificado de qualidade do dataset** (`laranjix certify`), em Markdown e
  JSON, recalculado a partir dos arquivos do dataset: privacidade, reprodutibilidade,
  fidelidade à calibração, utilidade (TSTR) e os limites declarados do que ele
  não afirma.
- Checagens de fidelidade por distância de variação total, com o limiar derivado
  do ruído amostral do próprio tamanho da amostra em vez de uma constante
  arbitrária.
- Harness TSTR (*train-on-synthetic, test-on-real*) com `scikit-learn` no extra
  `bench`. A base real de referência nunca entra no repositório: só a métrica sai.
- Job de CI que emite o certificado a cada push e o publica como artefato.
- **Movimentacao normal em Pix** (Marco 3): circulo de contrapartes recorrentes com
  estrutura de hubs, calendario brasileiro com feriados e dias de pagamento, curva
  horaria, concentracao em valores redondos e o limite noturno da Resolucao BCB
  142/2021.
- **Tipologias T1 (cadeia de contas laranja) e T2 (engenharia social)** (Marco 4),
  como plugins, com gabarito em arquivos separados: `labels_transactions`,
  `labels_accounts` e `cases`.
- **`label_available_at`**: o rotulo de fraude so passa a existir quando a vitima
  contesta, em ate 80 dias (MED). O split temporal respeita isso, entao fraudes ainda
  nao contestadas na data de corte sao treinadas como transacoes comuns.
- **Niveis de dificuldade** `easy`, `medium` e `hard`, com mulas que ja tem historico,
  valores tirados do historico da vitima e falsos positivos legitimos plantados.
- **Benchmark** (`laranjix benchmark`) com tres modelos de referencia e as metricas
  PR-AUC e recall a 1% de falso positivo, com media e desvio sobre varios treinos.
- **`laranjix generate`**: gera o dataset completo, nao so a populacao.
- Job de CI que roda o benchmark e publica a tabela no resumo da execucao.

### Desempenho

- Geração da população vetorizada: **11,9 mil → 105 mil contas/s (8,8×)**. Documentos,
  nomes, telefones e chaves EVP passam a ser gerados em lote, com os dígitos
  verificadores como produto de matrizes e a renderização de strings por buffer ASCII.
- O sorteio de tipos de chave Pix, que é restrito por conta, deixou de iterar conta a
  conta: a população inteira avança junta por posição de sorteio, com máscara de tipos
  ainda disponíveis. O mix realizado não muda.
- As buscas que cada tipologia faz por caso passaram a ser calculadas uma vez e
  cacheadas. Eram 121 varreduras completas da tabela de transações e 1.469 filtros de
  conta única por execução. **Dataset completo: 15,1 s → 5,1 s (3,0×).**
- Teste de regressão que falha se o custo voltar a crescer de forma não linear.

### Corrigido

- **Mix de chaves Pix não reproduzia a calibração.** Toda colisão de tipo único
  virava EVP, que saía com 42,7% contra um alvo de 31% (PF) — 18,6 vezes o que o
  ruído amostral explica. O gerador agora resolve analiticamente os pesos de
  sorteio cujo resultado é o alvo. Isso **muda a saída de seeds existentes**;
  como o projeto é pré-v0.1, nenhum dataset publicado é afetado.
- **Falso positivo do scanner em hashes.** Um SHA-256 do `manifest.json` continha uma
  corrida de digitos que passava no checksum de Luhn. Digests hexadecimais de 32 ou
  mais caracteres sao mascarados antes da varredura numerica.
- **Features de grafo com valores nulos.** O `rolling` do Polars colapsa linhas que
  compartilham o mesmo instante dentro de um grupo, entao o join por `tx_id` deixava
  buracos. Agora o casamento e por (conta, instante).
- **Nivel `medium` indistinguivel do `easy`.** Com os valores iniciais, o modelo de
  grafo marcava o mesmo nos dois, o que tornava o degrau do meio inutil.
- O marcador `laranjix-pii-fixture` só tem efeito dentro de `tests/`. Antes,
  qualquer arquivo que citasse o marcador — como a própria documentação que o
  descreve — se excluía da varredura.
