# Privacidade: por que nenhum dado deste projeto pode ser de alguém real

Este documento descreve como o Laranjix garante, na prática, o princípio central
do escopo: **nenhum dado pessoal real entra no projeto em nenhuma etapa** — nem
no código, nem nos parâmetros, nem nos datasets gerados, nem nas contribuições.

As cinco camadas abaixo correspondem à seção 5 do [ESCOPO.md](../ESCOPO.md).

## Camada 1 — Calibração só com dados agregados

O gerador é calibrado apenas com **estatísticas agregadas e públicas**: totais
mensais, distribuições por UF, contagens de fraude do MED. Microdados de
indivíduos nunca entram, e é proibido usar vazamentos, bases compradas, dados
raspados ou dados de clientes de qualquer empresa, mesmo "anonimizados".

Os parâmetros ficam em `src/laranjix/calibration/params/*.yaml`. Cada arquivo
declara a fonte dos seus números num bloco `meta`, e o carregador **recusa** um
arquivo sem fonte declarada. O comando abaixo lista tudo, com o estado de cada
parâmetro:

```bash
laranjix calibration
```

Parâmetros marcados como `provisorio` são valores de ordem de grandeza plausível,
transcritos à mão para destravar o gerador. O Marco 1 os substitui por números
derivados direto das APIs públicas, com o script de derivação versionado ao lado.

## Camada 2 — Identificadores impossíveis de coincidir com algo real

| Dado | Estratégia | Onde |
|------|------------|------|
| **CPF** | Os 9 dígitos base são aleatórios; os 2 dígitos verificadores são calculados pelo algoritmo oficial e então **substituídos por valores diferentes**. Nenhum CPF gerado passa na validação oficial, logo não pode pertencer a ninguém. | `privacy/identifiers.py::fake_cpf` |
| **CNPJ** | Mesma estratégia, sobre os 12 dígitos base. | `fake_cnpj` |
| **Nomes** | Combinação aleatória de prenomes e sobrenomes comuns. Um nome isolado pode coincidir com o de alguém, mas nunca vem acompanhado de documento válido, endereço ou qualquer atributo real. | `fake_name`, `fake_company_name` |
| **E-mail** | Apenas os domínios `example.com`, `example.org` e `example.net`, reservados pela [RFC 2606](https://www.rfc-editor.org/rfc/rfc2606). Esses domínios não podem ser registrados, então a mensagem nunca chega a ninguém. | `fake_email` |
| **Telefone** | DDD `00`. Os códigos de área brasileiros começam em 11; um DDD com zero à esquerda não existe e não pode ser discado. | `fake_phone` |
| **Chave aleatória (EVP)** | UUID gerado localmente a partir do fluxo determinístico da geração. | `evp_key` |
| **Instituições** | `inst_01`, `inst_02`… Nenhum nome de banco, código de compensação ou ISPB real. | `institution_id` |
| **Endereços** | Não são gerados. Apenas a UF. | — |

### Sobre a escolha do formato de telefone

Esta é a questão aberta 1 do escopo, resolvida assim: DDD `00`. As alternativas
consideradas foram usar um DDD válido com prefixo não atribuído (frágil, porque
a atribuição muda) ou uma faixa reservada de teste (não existe equivalente
brasileiro estável). Um DDD com zero à esquerda é inválido por estrutura do
plano de numeração, não por uma decisão administrativa que pode mudar.

## Camada 3 — Checagens automáticas

Duas verificações, ambas rodando no CI a cada push e pull request.

**1. Prova de invalidade dos documentos.** `privacy/validators.py` implementa os
algoritmos **oficiais** de CPF e CNPJ. Eles nunca são usados para gerar nada —
existem só para que os testes provem que todo documento gerado é inválido. Os
testes verificam isso sobre 5.000 documentos de cada tipo e contra documentos de
exemplo conhecidamente válidos, para garantir que o validador funciona.

**2. Scanner de PII.** `privacy/scan.py` procura, em qualquer arquivo ou pasta,
tudo que **poderia** ser real:

| Categoria | O que dispara |
|-----------|---------------|
| `valid_cpf` | Sequência de 11 dígitos que passa nos dígitos verificadores oficiais |
| `valid_cnpj` | Sequência de 14 dígitos que passa nos dígitos verificadores oficiais |
| `luhn_card` | Sequência de 13 a 19 dígitos que passa no checksum de Luhn |
| `non_reserved_email` | E-mail em domínio fora da RFC 2606 |
| `dialable_phone` | Telefone com DDD brasileiro válido |

O scanner nunca imprime o valor completo de um achado: ele mostra apenas os dois
primeiros e os dois últimos caracteres. Rodar manualmente:

```bash
laranjix privacy-check out/          # nos dados gerados
laranjix privacy-check .             # no repositório inteiro
```

### Falsos positivos já tratados

O scanner é deliberadamente agressivo, e isso produziu três falsos positivos
reais durante o desenvolvimento. Todos estão travados por teste:

1. **CNPJ lido como cartão.** Um CNPJ tem 14 dígitos e às vezes passa no Luhn por
   acaso. Um documento com a pontuação oficial (`00.000.000/0000-00`) agora é
   checado apenas como documento.
2. **Telefone fictício lido como cartão.** `+5500…` tem 13 dígitos e às vezes
   passa no Luhn. Sequências precedidas de `+` são tratadas como telefone.
3. **UUID lido como cartão ou telefone.** Os grupos hexadecimais de um UUID são
   unidos por hífens, então uma corrida de dígitos pode atravessar dois grupos e
   formar tanto um número Luhn-válido quanto um padrão de telefone. UUIDs são
   mascarados antes das varreduras numéricas. Foi o que apareceu ao gerar 50 mil
   contas, e não aparecia em 5 mil.
4. **Remote SSH lido como e-mail.** `git@github.com:owner/repo.git` casa com o
   padrão de e-mail, mas é uma URL, não uma caixa postal. Um endereço seguido de
   `:` e um caminho é ignorado.

Nenhuma dessas exceções enfraquece a detecção de dado real: um cartão ou telefone
verdadeiro não tem a forma de um UUID, um documento real não vem com a pontuação
trocada, e um endereço de e-mail não é seguido por um caminho de repositório.

### A única forma de excluir um arquivo do scanner

Os testes do próprio scanner precisam conter valores que o façam disparar. Para
isso existe **um** mecanismo, e ele é explícito:

```python
# laranjix-pii-fixture
```

Um arquivo de texto que contenha esse marcador nos primeiros 4 KB é ignorado por
inteiro. A exclusão nunca é silenciosa: todo arquivo ignorado é listado na saída
do `laranjix privacy-check`. O módulo que define o marcador não se exclui a si
mesmo — isso é verificado por teste.

Regras de uso: apenas arquivos dentro de `tests/`, e apenas quando o propósito do
arquivo for exercitar o scanner. Usar o marcador para "silenciar" um achado em
código ou em dado gerado é exatamente o tipo de mudança que o `SECURITY.md` trata
como incidente.

## Camada 4 — Governança de contribuições

- `CONTRIBUTING.md` proíbe explicitamente submeter dados reais, mesmo anonimizados.
- Novas tipologias exigem **fonte pública**; não aceitamos tipologias baseadas em
  casos internos de empresas.
- `CODEOWNERS` exige revisão de mantenedor para qualquer mudança em
  `src/laranjix/privacy/` e `src/laranjix/calibration/`.
- O `.gitignore` bloqueia arquivos de dados brutos fora das pastas permitidas.

## Camada 5 — Transparência no dataset

Toda geração escreve um `manifest.json` com a versão do Laranjix, a configuração
completa, a seed, o hash de cada arquivo, o *fingerprint* dos parâmetros de
calibração, quais deles são provisórios e a declaração de que o dataset é 100%
sintético e não demonstra desempenho em produção.

## LGPD

Como o projeto não coleta nem trata dados pessoais reais, a LGPD (Lei nº
13.709/2018) não incide sobre os datasets gerados. As camadas acima existem
justamente para que isso continue verdadeiro. Recomenda-se revisão jurídica
antes da primeira release pública.

## Encontrou um problema?

Se você encontrar um documento gerado que seja **válido**, um identificador que
possa corresponder a algo real, ou dado pessoal real em qualquer lugar do
repositório: **não abra issue pública**. Siga o `SECURITY.md`. Tratamos como
incidente, não como bug comum.
