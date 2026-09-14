# Relatório — Open Finance Etapa 2G: demonstração para testers

## Objetivo

Preparar a Nivra para que uma pessoa sem contexto técnico possa testar a integração Open Finance exclusivamente no Sandbox da Pluggy.

## Experiência entregue

A página **Contas** passou a apresentar um guia curto de primeiro uso dentro da área de Open Finance. Ele mostra o progresso entre conectar um banco de demonstração, atualizar os dados, vincular a conta à Nivra e consultar as movimentações.

O fluxo mantém os indicadores já existentes da Etapa 2F: instituição, estado da conexão, última atualização, contas externas, saldo, quantidade de movimentações, origem bancária e vínculo com a conta Nivra. Cartões externos continuam apenas para consulta.

O card identifica o ambiente como **Demonstração** e oferece, em uma área expansível, as credenciais fictícias oficiais do Pluggy Bank:

- usuário `user-ok`;
- senha `password-ok`;
- MFA `123456`.

A mesma área informa que credenciais bancárias reais nunca devem ser usadas. Não foram adicionadas credenciais de usuário Nivra, secrets Pluggy ou qualquer configuração de produção ao frontend.

## Primeiro uso sem dados

Foram ajustadas as mensagens vazias para orientar sem criar um wizard:

- **Contas:** sugere conta manual ou banco de demonstração;
- **Dashboard:** indica que a conta pode ser adicionada ou conectada em Contas;
- **Transações:** explica que o histórico pode começar com lançamento manual ou sincronização Sandbox.

## Guia para testers

O procedimento, checklist de regressão, repetição segura da sincronização, modelo de relato de bug e orientações sobre dados proibidos foram reunidos em [open-finance-sandbox.md](testing/open-finance-sandbox.md).

Não existe botão de reset destrutivo. A repetição recomendada é usar **Atualizar dados** na mesma conexão, cuja sincronização já é idempotente. Para repetir uma primeira conexão limpa, o tester deve criar outra conta Nivra própria.

## Validação da publicação 2F

Antes desta etapa, a versão 2F foi confirmada em `https://nivra-finance.vercel.app/accounts` após o deploy do commit `25a4007`:

- área “Suas conexões bancárias” publicada;
- selo de demonstração visível;
- estado conectado e estado de erro apresentados com linguagem compreensível;
- conta externa, saldo, quantidade de movimentações e vínculo exibidos;
- conta Nivra vinculada marcada como banco conectado;
- nenhum erro técnico, Item ID ou secret exposto na interface.

O fluxo de abertura do modal de vínculo foi preservado. Nenhuma alteração financeira foi salva durante a validação de produção.

## Limitações conhecidas

- O ambiente continua estritamente em `OPEN_FINANCE_ENVIRONMENT=sandbox`.
- A implementação foi validada localmente e na produção desktop; a confirmação por testers independentes, incluindo navegadores e dispositivos móveis reais, permanece como validação operacional pendente.
- Não há conexão com banco real ou Pluggy Production.
- Reconexão e desconexão ainda não são oferecidas porque não existe um fluxo backend/provider completo e seguro.
- A confirmação externa do comportamento idempotente de entrega repetida por webhook ainda é pendente; a Etapa 2E não foi marcada como concluída por esta etapa.
- A validação de uso por testers independentes é o próximo passo operacional, não uma afirmação automática de que todos os dispositivos foram testados em produção.

## Próxima tarefa recomendada

**Etapa 2H — Conciliação avançada.**

Ela deverá melhorar correspondências entre dados manuais e bancários, sem ser iniciada como parte desta entrega.
