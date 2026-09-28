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
