# Roteiro de fundamentação

Este documento responde a uma pergunta só: **o que impede o Laranjix de virar um
gerador que ensina a máquina as suposições de quem o escreveu?**

## O risco, nomeado com precisão

O medo comum é o *colapso de modelo* — IA treinando na saída de IA, perdendo as
caudas da distribuição a cada geração. **Não é o risco deste projeto.** O
Laranjix não aprende nada: é um simulador paramétrico, regras e distribuições
escritas à mão. Não há laço recursivo porque não há modelo sendo ajustado a
dados.

O risco real é mais silencioso:

> Os números que definem o que é "normal" e o que é "fraude" foram escritos por
> quem montou os arquivos. Se nada externo os sustenta, o dataset descreve uma
> **suposição**, e todo modelo treinado nele aprende a suposição como se fosse
> medição.

Nada quebra. Os testes passam. O benchmark fica bonito. É por isso que precisa
de processo, e não de boa intenção.

## Onde a suposição entra

Sete superfícies. A tabela é o escopo deste roteiro:

| # | Superfície | Estado |
|---|---|---|
| 1 | Parâmetros de calibração | 1 de 5 fundamentado |
| 2 | Assinaturas das tipologias | T1 e T2 citadas, 4 lacunas declaradas |
| 3 | Níveis de dificuldade | Sem fonte, e **fora** do sistema de proveniência |
| 4 | Regras estruturais do gerador | Dentro de `behavior.yaml`, sem fonte própria |
| 5 | Desenho do benchmark | Parcialmente circular, documentado |
| 6 | Alvo da validação | Compara com a calibração, não com a realidade |
| 7 | Tipologias futuras (T3–T6) | Nada escrito ainda |

---

## F0 — Tornar o invisível visível ✅

*Resultado: uma suposição não declarada deixa de ser possível.*

- [x] Toda proveniência declarada por arquivo, com a evidência que o tipo exige.
- [x] Carregador **recusa** arquivo que afirme mais do que mostra.
- [x] `laranjix calibration` lista cada parâmetro e o que falta nele.
- [x] `laranjix calibration --require-grounded` sai 1 — o gate de release.
- [x] Certificado nomeia os parâmetros sem fundamento em todo dataset gerado.
- [x] `CONTRIBUTING.md` proíbe parâmetro ou tipologia entrar na autoridade de um
      modelo.
- [x] Tipologias registram **o que as fontes não sustentam** (`sources.yaml`).

Sem este marco os outros não são verificáveis: dá para dizer que algo é
fundamentado sem que ninguém consiga conferir.

## F1 — Parâmetros derivados das fontes

*Resultado: nenhum número estatístico é digitado à mão.*

- [x] `population_uf` — API do IBGE, com script versionado e hash da resposta.
- [ ] `pix_keys` — estoque de chaves por tipo, API OData do BCB.
- [ ] `behavior` — volume e ticket médio, Estatísticas do Pix do BCB.
- [ ] `accounts` — porte e idade de empresas (Dados Abertos do CNPJ, agregado);
      faixas de renda e mix PF/PJ (IBGE).
- [ ] `names` — não é estatística. Vai para F3 (revisão) ou lista pública.

**Critério de saída:** `laranjix calibration --require-grounded` sai 0.

**Padrão já estabelecido** por `population_uf`, e que os próximos devem seguir:
script versionado em `calibration/derive/`, `retrieved_at`, e **SHA-256 da
resposta** — é o hash que depois distingue "a fonte mudou" de "alguém editou o
arquivo".

## F2 — Fechar as lacunas das tipologias

*Resultado: o que o gerador inventou está escrito, ou deixou de ser invenção.*

Lacunas declaradas hoje:

| Tipologia | Sem fonte |
|---|---|
| T1 | A cadeia multi-salto (a fonte descreve saque, não repasse encadeado) |
| T1 | O intervalo entre saltos |
| T2 | O fan-in concentrado |
| T2 | Nº de vítimas por caso e largura da janela |

- [ ] Procurar na Carta Circular BCB nº 4.001/2020 e nos relatórios do GAFI
      descrição de encadeamento entre contas e de concentração de vítimas.
- [ ] Buscar nos comunicados oficiais do BCB sobre golpes do Pix números de
      vítimas por caso.
- [ ] O que sobrar sem fonte vai para F3.

**Critério de saída:** nenhuma lacuna na *assinatura central* de uma tipologia —
parâmetro de ajuste sem fonte é tolerável, a forma do padrão não é.

## F3 — Revisão humana

*Resultado: alguém que vê fraude em produção olhou e discordou ou concordou.*

- [ ] Encontrar revisor (o pedido pronto está em
      [typologies/revisao.md](typologies/revisao.md)).
- [ ] Revisar T1 e T2: assinatura, o que está exagerado, **quais falsos
      positivos aparecem na prática**.
- [ ] Revisar os níveis de dificuldade — quais mecanismos de camuflagem
      realmente atrapalham.
- [ ] Revisar o vocabulário de nomes.
- [ ] Registrar como `expert_review`, com credencial e escopo. Discordância fica
      escrita, não é apagada.

**Critério de saída:** T1, T2 e os presets de dificuldade com `reviewed_by`.

A pergunta dos falsos positivos é a mais valiosa: é o que o dataset tem menos
condição de inventar sozinho, e é o que separa um benchmark difícil de um fácil.

## F4 — Trazer a dificuldade para dentro do sistema

*Resultado: os controles de camuflagem param de ser invisíveis.*

Hoje `DIFFICULTY_PRESETS` vive em `config.py`, declarado só num docstring. É a
única superfície importante **fora** do sistema de proveniência — e é ela que
define o quanto o benchmark é difícil.

- [ ] Mover os presets para um arquivo com `meta.provenance`.
- [ ] Declarar `unverified` com `to_ground` honesto.
- [ ] Fazer o certificado nomeá-los junto com os parâmetros.

**Critério de saída:** `laranjix calibration` lista a dificuldade como qualquer
outro parâmetro.

## F5 — Medir contra a realidade, não contra si mesmo

*Resultado: um número que vem de fora do projeto.*

Hoje a fidelidade compara o gerado com a **calibração** — mede se o gerador
obedece, não se o alvo é real. E o resultado do benchmark é parcialmente
circular: fraudes com forma de grafo são achadas por features de grafo porque
foram postas assim.

- [ ] TSTR contra uma base real, na máquina de quem a possui. Só a métrica sai.
- [ ] Comparar distribuições geradas com as **estatísticas publicadas** do BCB,
      não com os parâmetros.
- [ ] Comparar dificuldade com AMLworld, AMLSim, SAML-D e PaySim.

**Critério de saída:** o README cita pelo menos um número medido fora do
projeto.

## F6 — Impedir o retrocesso

*Resultado: fundamentado hoje continua fundamentado em dois anos.*

Fonte envelhece. Censo é recenseado, API muda de recurso, tipologia some da
coletânea seguinte. Nada disso falha ruidosamente.

- [ ] Job agendado que re-executa as derivações e compara com o `source_sha256`
      gravado, abrindo issue quando a fonte mudar.
- [ ] `retrieved_at` com mais de 24 meses vira aviso no certificado.
- [ ] Revisão de especialista com validade declarada.
- [ ] `--require-grounded` no pipeline de release, não só disponível na CLI.

**Critério de saída:** a fonte mudar gera alarme sem ninguém estar olhando.

## F7 — Aplicar a régua às tipologias novas

*Resultado: T3–T6 nascem fundamentadas, em vez de serem corrigidas depois.*

- [ ] T3 (pulverização) — COAF 2021, tipologia 2.76 "Fracionamento Cooperativo"
      e Resolução BCB nº 142/2021 (limite noturno) são ponto de partida.
- [ ] T5 (lavagem em ciclo) — coletânea do COAF de 2016, que traz fluxogramas.
- [ ] T4 (empresas de fachada) — Carta Circular 4.001 cita sócios sem capacidade
      financeira para o porte.
- [ ] T6 (boleto) — COAF 2021, tipologia 2.35 "Fraude via Falsificação de
      Boletos Bancários".

**Critério de saída:** nenhuma tipologia entra sem `grounded_by` com página e
trecho literal, e sem `not_supported_by_sources` preenchido.

---

## O que não resolvemos, e por quê

**Dado real não entra.** Em dados transacionais, [4 pontos espaço-temporais
reidentificam 90% das pessoas](https://www.science.org/doi/10.1126/science.1256297).
O que identifica não é o CPF, é o padrão — e a topologia que torna o dataset
útil é a impressão digital do caso real. Fundamento vem de **agregados públicos
e de revisão humana**, não de cópia de registro.

**Código gerado por modelo não é o problema central.** Código errado quebra
teste. Número errado não quebra nada — vira verdade.

## Como saber que funcionou

Quando as três frases abaixo forem verdadeiras ao mesmo tempo:

1. `laranjix calibration --require-grounded` sai 0.
2. Toda tipologia cita página e trecho, e declara o que não é citado.
3. O README mostra ao menos um número medido **fora** do projeto.
