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

## 4. Contribuindo com uma nova tipologia de fraude

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

## 5. O que o CI verifica

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

## 6. Reprodutibilidade

Toda geração é determinística: mesma `seed` + mesma config = mesmo dataset. Se
uma mudança sua altera a saída para uma seed existente, diga isso no PR e
explique por quê. Mudanças que quebram reprodutibilidade entram só em releases
com bump de versão menor.

## 7. Código de conduta

Ao participar, você concorda com o `CODE_OF_CONDUCT.md`.
