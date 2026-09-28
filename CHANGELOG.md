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

### Corrigido

- O marcador `laranjix-pii-fixture` só tem efeito dentro de `tests/`. Antes,
  qualquer arquivo que citasse o marcador — como a própria documentação que o
  descreve — se excluía da varredura.
