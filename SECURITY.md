# Política de segurança

## Como reportar

**Não abra uma issue pública** para vulnerabilidades ou suspeitas de vazamento
de dados. Use o [Private Vulnerability Reporting](https://github.com/mkmuniz/Laranjix/security/advisories/new)
do GitHub. A resposta inicial acontece em até 5 dias úteis.

## O que consideramos vulnerabilidade

Além dos problemas usuais de segurança de código e dependências, tratamos como
vulnerabilidade **crítica** deste projeto:

1. Um documento gerado (CPF ou CNPJ) que seja **válido** pelo algoritmo oficial
   de dígitos verificadores. Por construção, isso nunca deve acontecer
   (ver `docs/privacy.md`).
2. Qualquer identificador gerado que possa corresponder a algo real: e-mail fora
   dos domínios reservados pela RFC 2606, telefone em faixa de numeração válida,
   nome de instituição real ou ISPB real.
3. Presença de dados pessoais reais em qualquer lugar do repositório, incluindo
   histórico do Git, parâmetros de calibração, testes e fixtures.

Se você encontrar qualquer um desses casos, reporte em privado. Trataremos como
incidente, não como bug comum.

## Fora de escopo

- O fato de o projeto descrever tipologias de fraude. Todas as tipologias se
  limitam ao que já é público em normas e publicações oficiais, e são descritas
  do ponto de vista de quem detecta (ESCOPO.md, seção 5.6).
- Resultados de modelos treinados nos datasets gerados. Eles são sintéticos e
  não demonstram desempenho em produção.

## Versões suportadas

Enquanto o projeto estiver antes da 1.0, apenas a última versão publicada
recebe correções.
