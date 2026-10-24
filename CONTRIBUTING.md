# Como contribuir

Obrigado pelo interesse no Laranjix. Antes de qualquer coisa, leia a regra
número um.

## 1. Regra número um: nenhum dado real, nunca

**É proibido enviar ao projeto dados pessoais reais**, em qualquer formato, em
qualquer pasta, em qualquer etapa — código, testes, fixtures, parâmetros de
calibração, exemplos em issues ou prints em pull requests.

Isso inclui, sem exceção:

- microdados de pessoas ou empresas, **mesmo anonimizados ou pseudonimizados**;
- dados de clientes de qualquer empresa, mesmo que você tenha acesso legítimo a eles;
- bases compradas, dados raspados de redes sociais e dados de vazamentos;
- CPFs, CNPJs, telefones, e-mails ou nomes completos de pessoas reais, mesmo o seu.

Só entram no projeto **estatísticas agregadas e públicas**, com a fonte citada.
Um PR que viole essa regra é fechado sem revisão. Se você perceber que enviou
algo indevido, avise imediatamente pelo canal do `SECURITY.md` — o histórico do
Git precisa ser reescrito, e isso é tratado como incidente.

## 2. Ambiente de desenvolvimento

```bash
git clone git@github.com:mkmuniz/Laranjix.git
cd Laranjix
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Verificação antes de abrir o PR:

```bash
ruff check . && ruff format --check .
mypy src
pytest
laranjix privacy-check out/            # se você gerou dados localmente
```

## 3. Commits e branches

- Commits seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/):
  `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- Uma branch por assunto, a partir da `main`.
- Documentação do repositório, nomes de código e mensagens de commit em inglês.
  Documentos de escopo e páginas de tipologia em português.

## 4. Nada entra só porque um modelo disse

Um gerador define, em números, o que conta como comportamento normal e o que
conta como fraude. Se esses números vierem de um modelo de linguagem, ou da
intuição de quem escreveu o arquivo, o dataset deixa de descrever o Brasil e
passa a descrever uma suposição — e todo modelo treinado nele aprende a
suposição como se fosse medição. Esse é um erro silencioso: nada quebra, os
testes passam, e o benchmark continua bonito.

Por isso **todo parâmetro de calibração declara sua proveniência**, e a
declaração tem que sustentar o que afirma:

| Proveniência | O que o arquivo precisa mostrar |
|---|---|
| `regulatory` | A norma que fixa o valor (ex.: Resolução BCB 142/2021) |
| `public_statistic` | `source_url` e `retrieved_at` — qual fonte, lida quando |
| `expert_review` | `reviewed_by` e `reviewed_at` — quem revisou, com que credencial |
| `unverified` | `note` e `to_ground`: o que falta e qual é o passo concreto |

O carregador **recusa** um arquivo que afirme mais do que mostra. Citar "BCB"
sem dizer qual recurso e qual data falha igual a não citar nada.

`unverified` é legítimo enquanto se constrói — um gerador não pode esperar toda
fonte estar lida para rodar a primeira vez. Não é legítimo numa release:

```bash
laranjix calibration --require-grounded   # sai 1 se algo ainda for unverified
```

O mesmo vale para tipologias: uma assinatura de fraude precisa de fonte pública
(seção 5) ou de revisão por profissional de prevenção à fraude, registrada em
`reviewed_by`. "Parece plausível" não é proveniência.

## 5. Contribuindo com uma nova tipologia de fraude

Cada tipologia é um plugin em `src/laranjix/typologies/<nome>.py`. Um PR de
tipologia só é aceito com:

1. **Fonte pública** que fundamente o padrão — norma do Banco Central, publicação
   do COAF, relatório do GAFI/FATF, comunicado oficial. Não aceitamos tipologias
   baseadas em casos internos de empresas nem em informação que você não possa
   compartilhar publicamente.
2. Uma página em `docs/typologies/` descrevendo o padrão **do ponto de vista de
   quem detecta**: qual é a assinatura no grafo e por que ela aparece.
3. Rotulagem completa no gabarito: tipologia, `case_id` e papel de cada conta.
4. Testes que verifiquem a assinatura esperada no grafo gerado.

Não aceitamos contribuições que ajudem a **executar** fraudes: otimização contra
detectores específicos, passo a passo operacional de golpes ou técnicas de evasão.

## 6. O que o CI verifica

Todo PR passa por:

| Checagem | O que falha o build |
|----------|---------------------|
| Validador de documentos | Qualquer CPF/CNPJ gerado que seja **válido** pelo algoritmo oficial |
| Scanner de PII | E-mail fora dos domínios reservados, telefone em faixa válida, cartão com Luhn válido, CPF/CNPJ válido em texto |
| Checagem de arquivos | Arquivo de dados brutos (`.csv`, `.parquet`, `.xlsx`) fora das pastas permitidas |
| Lint, tipos e testes | `ruff`, `mypy`, `pytest` |
| Reprodutibilidade | A mesma seed gerando dois datasets diferentes |
| CodeQL e Dependabot | Vulnerabilidades no código e nas dependências |

O scanner tem **um** mecanismo de exclusão: o marcador `laranjix-pii-fixture`
dentro do arquivo, e ele só funciona dentro de `tests/` — fora dali é texto
comum. Serve para os arquivos cujo propósito é exercitar o próprio scanner.
Arquivos ignorados são sempre listados na saída. Usar o marcador para silenciar
um achado em código ou em dado gerado é tratado como incidente (ver
`SECURITY.md`), não como atalho.

## 7. Reprodutibilidade

Toda geração é determinística: mesma `seed` + mesma config = mesmo dataset. Se
uma mudança sua altera a saída para uma seed existente, diga isso no PR e
explique por quê. Mudanças que quebram reprodutibilidade entram só em releases
com bump de versão menor.

## 8. Código de conduta

Ao participar, você concorda com o `CODE_OF_CONDUCT.md`.
