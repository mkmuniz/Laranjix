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

## Certificado de qualidade

Todo dataset gerado pode emitir um **certificado verificável**. Ele não é um selo
decorativo: cada linha é recalculada a partir dos arquivos do dataset, e qualquer pessoa
reproduz o resultado com um comando.

```bash
laranjix generate-population --accounts 50000 --seed 42 --out out/
laranjix certify out/
```

```
Privacidade          nenhum documento valido e nenhum achado de PII
Reprodutibilidade    a seed 42 reproduziu 8 arquivo(s) byte a byte
Fidelidade           9 distribuicoes, pior caso 0.7x o ruido
Utilidade (TSTR)     o dataset ainda nao tem rotulos de fraude; TSTR entra com o Marco 4
certificado          out/certificate.md
```

O certificado tem cinco seções, e sai também em JSON (`certificate.json`) para automação:

| Seção | O que é recalculado | Como se prova |
|-------|---------------------|---------------|
| **1. Privacidade** | Todo documento é revalidado pelo algoritmo oficial e todo arquivo é varrido | `0` documentos válidos, `0` achados de PII |
| **2. Reprodutibilidade** | O dataset é regerado a partir do próprio `manifest.json` | SHA-256 de 8 de 8 arquivos idênticos |
| **3. Fidelidade** | 9 distribuições comparadas com os alvos da calibração | Distância de variação total × ruído amostral |
| **4. Utilidade (TSTR)** | Modelo treinado no sintético, avaliado em base real | Razão TSTR/TRTR — pendente até o Marco 4 |
| **5. Limites** | O que o certificado **não** afirma | Declarado por escrito |

### A seção 3, em detalhe

Comparar distribuições precisa de um limiar honesto: nenhuma amostra finita reproduz
exatamente o alvo. O limiar de cada checagem é o desvio que **o próprio tamanho da
amostra produz**, estimado por simulação no percentil 99,9. Uma checagem só falha quando
o desvio é maior do que o acaso explica.

| Distribuição | TVD | Limiar de ruído | × ruído | |
|---|---:|---:|---:|---|
| UF das contas | 0.00884 | 0.01250 | 0.7× | PASSOU |
| Tipo de titular (PF/PJ/MEI) | 0.00150 | 0.00403 | 0.4× | PASSOU |
| Tipo de chave Pix (PF) | 0.00238 | 0.00624 | 0.4× | PASSOU |
| Chaves por conta | 0.00108 | 0.00765 | 0.1× | PASSOU |

*(4 das 9 linhas; o certificado completo sai em `out/certificate.md`. A metodologia está em [docs/quality.md](docs/quality.md).)*

Esse teste já pagou por si: ao rodar pela primeira vez, ele reprovou o mix de chaves Pix
com **18,6× o ruído** — EVP saía com 42,7% contra um alvo de 31%. Era um defeito real do
gerador, [documentado e corrigido](docs/quality.md#o-primeiro-defeito-que-o-certificado-pegou).

### O que o certificado não afirma

Ele compara o dataset com os **parâmetros de calibração**, não com a realidade. Um
dataset pode passar em tudo e continuar irrealista se os parâmetros estiverem errados —
e os parâmetros de hoje ainda são provisórios. O certificado nomeia quais são, toda vez.

Medir realismo contra a realidade é o papel do **TSTR**: treinar no sintético e avaliar
numa base real. A base real fica na máquina de quem a possui e **nunca entra no
repositório** — só o número sai. Metodologia em [docs/quality.md](docs/quality.md).

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
| — | Certificado de qualidade verificável (`laranjix certify`) | ✅ |
| 1 | Calibração com números derivados das fontes públicas | 🚧 parâmetros provisórios |
| 3 | Movimentação normal (Pix, TED, boleto, débito) | ⬜ |
| 4 | Primeiras fraudes rotuladas (T1, T2) → v0.1 | ⬜ |

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
laranjix generate-population --accounts 50000 --seed 42 --out out/
```

```
accounts              50,000 linhas
pix_keys             105,595 linhas
company_partners       7,141 linhas
institutions              12 linhas
manifest           out/manifest.json
privacidade: nenhum achado.
```

Outros comandos:

```bash
laranjix calibration          # fontes e estado de cada parâmetro
laranjix certify out/         # emite o certificado de qualidade do dataset
laranjix privacy-check out/   # varredura de PII em qualquer arquivo ou pasta
laranjix generate-population --config exemplo.yaml
```

Configuração por arquivo:

```yaml
# exemplo.yaml
seed: 42
difficulty: medium
formats: [parquet, csv]
output_dir: out
population:
  accounts: 50000
  reference_date: 2026-01-01
```

## Reprodutibilidade

Mesma `seed` + mesma configuração = mesmo dataset, byte a byte. Cada geração escreve um
`manifest.json` com a versão do Laranjix, a configuração completa, a seed, o hash de cada
arquivo e o *fingerprint* dos parâmetros de calibração usados.

Cada etapa do pipeline sorteia de um fluxo próprio, derivado da seed e do nome da etapa. Assim,
acrescentar uma etapa nova não desloca os números sorteados pelas etapas existentes.

## Modelo de dados

Hoje o gerador produz quatro tabelas, em Parquet e CSV:

| Tabela | Conteúdo |
|--------|----------|
| `accounts` | Contas PF/PJ/MEI com documento fictício, UF, instituição, data de abertura, faixa de renda e perfil de uso |
| `pix_keys` | Chaves Pix (`cpf`, `cnpj`, `email`, `phone`, `evp`) com data de cadastro |
| `company_partners` | Arestas de sociedade entre PF e PJ — base da tipologia de empresas de fachada |
| `institutions` | Instituições fictícias (`inst_01`…), nunca um banco ou ISPB real |

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
