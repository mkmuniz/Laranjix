# Revisão das tipologias por quem trabalha com fraude

Este documento existe para que pedir uma revisão custe **20 minutos** de quem
revisa, não três horas. Ele é o pacote que se envia a um profissional de
prevenção à fraude, e o formato em que a resposta volta para o repositório.

## Por que isso importa mais do que parece

O Laranjix define, em números e regras, o que conta como comportamento normal e
o que conta como fraude. Hoje essas definições são `unverified`: foram escritas
por quem montou os arquivos, sem nada externo para sustentá-las. Um modelo
treinado no dataset aprende essa suposição como se fosse medição.

Há três formas de sair disso, e **duas não dependem de encontrar ninguém**:

| Caminho | Depende de pessoa? | Estado |
|---|---|---|
| Fundamentar em fonte pública (COAF, GAFI, BCB) | Não | ⬜ a fazer |
| TSTR contra base real | Só de quem já tem a base | ⬜ a fazer |
| Revisão por profissional | Sim | ⬜ este documento |

As publicações do COAF e do GAFI **são escritas por especialistas** e descrevem
tipologias reais com fluxogramas do caminho do dinheiro. Citar uma tipologia
específica dessas publicações é fundamento externo de verdade, e não exige
conhecer ninguém. É o caminho mais barato e deve vir primeiro.

A revisão humana continua valendo por uma coisa que documento nenhum dá: se a
assinatura que o gerador produz é **reconhecível por quem a vê em produção**.

## O pedido, curto o bastante para ser lido

> O Laranjix é um gerador open source de dados **sintéticos** de transações
> brasileiras, com fraudes plantadas e rotuladas, para treinar e avaliar modelos
> de detecção. Nenhum dado real é usado: os CPFs e CNPJs têm dígitos
> verificadores inválidos por construção.
>
> Estamos pedindo revisão de duas tipologias — cadeia de contas laranja e golpe
> de engenharia social. Não precisamos de nenhuma informação confidencial, nem
> de nada que a sua instituição não possa divulgar. A pergunta é só: **o padrão
> que descrevemos se parece com o que você vê?**
>
> São cinco perguntas, uma página. Crédito público no repositório, se quiser.

## As cinco perguntas

Para **cada** tipologia (T1 e T2), com a descrição em
[README.md](README.md) desta pasta em mãos:

1. **A assinatura está certa?** O padrão descrito no grafo corresponde ao que
   você observa? O que está faltando?
2. **O que está exagerado?** Algum parâmetro está fora da realidade — número de
   camadas, intervalo entre saltos, valores envolvidos?
3. **O que torna difícil de verdade?** Dos quatro mecanismos de camuflagem que
   usamos (mula com histórico, valor tirado do histórico da vítima, intervalo
   largo, falso positivo legítimo), qual é o que realmente atrapalha, e qual é
   irrelevante?
4. **O que mais gera falso positivo na prática?** Que comportamento legítimo é
   confundido com essa tipologia com mais frequência?
5. **O que mudou nos últimos dois anos?** Em especial depois do MED 2.0 e das
   regras de fevereiro de 2026.

A pergunta 4 costuma ser a mais valiosa: é a que o dataset tem menos condição de
inventar sozinho, e é o que separa um benchmark difícil de um fácil.

## Como a resposta entra no repositório

A revisão vira proveniência verificável. No arquivo da tipologia ou do
parâmetro revisado:

```yaml
meta:
  provenance: expert_review
  reviewed_by: "Nome Sobrenome — cargo, instituição (ou 'profissional de
    prevenção à fraude, 12 anos, instituição não identificada a pedido')"
  reviewed_at: 2026-11-15
  review_scope: "T1: profundidade de cadeia e intervalo entre saltos"
  review_notes: >-
    Resumo do que mudou por causa da revisão.
```

Regras:

- **Anonimato é aceitável**, credencial vaga não é. "Trabalha com fraude" não
  diz nada; "analista sênior de prevenção a fraudes em instituição de pagamento,
  8 anos" diz, mesmo sem nome.
- **A revisão tem escopo.** Alguém que revisou a profundidade das cadeias não
  carimba o dataset inteiro.
- **Discordância é registrada**, não apagada. Se o revisor disser que algo está
  errado e nós mantivermos, o motivo fica escrito.
- Mudanças em `provenance` passam pelo CODEOWNERS, como todo o resto de
  `calibration/`.

## Onde encontrar essas pessoas

Nenhuma destas é recomendação nem endosso — é só onde profissionais da área se
reúnem publicamente no Brasil:

| Onde | O que é |
|---|---|
| [ACFE Brasil](https://www.acfe.com.br/) | Capítulo brasileiro da associação de examinadores de fraude certificados |
| [ABIF](https://abif.com.br/) | Associação Brasileira de Investigadores de Fraudes |
| [ANCAF](https://www.ancaf.org.br/index.asp) | Associação Nacional de Combate a Fraudes |
| [Abecs](https://abecs.org.br/gestao-unificada-de-fraudes) | Associação das empresas de cartões, com fórum de combate à fraude |
| [woovibr/awesome-pix](https://github.com/woovibr/awesome-pix) | Comunidade técnica de Pix, onde o projeto pretende se divulgar |

Abrir uma issue pública no repositório pedindo revisão também funciona, e deixa
o pedido rastreável.

## Fontes que substituem parte da revisão

Estas são escritas por especialistas e são públicas. Fundamentar as tipologias
nelas é trabalho que pode ser feito hoje, sem depender de ninguém:

- **COAF — Casos & Casos, Tipologias, edição especial ANR (2021)**: 87
  tipologias. [gov.br](https://www.gov.br/coaf/pt-br/assuntos/o-sistema-de-prevencao-a-lavagem-de-dinheiro/avaliacao-nacional-de-riscos/2-2_casos-e-casos-tipologias-edicao-especial-anr.pdf/view)
- **COAF — Coletânea completa (2016)**: casos com fluxograma do caminho do
  dinheiro. [gov.br](http://www.gov.br/coaf/pt-br/centrais-de-conteudo/publicacoes/publicacoes-do-coaf-1/casosecasos_coletanea-completa_setembro2016.pdf)
- **Carta Circular BCB nº 4.001/2020**: lista oficial de situações que podem
  indicar lavagem de dinheiro.
- **Resolução BCB nº 493/2025 (MED 2.0)**: rastreamento em cadeia, que
  parametriza a profundidade de T1.
- **GAFI/FATF**: relatórios de tipologias internacionais.
