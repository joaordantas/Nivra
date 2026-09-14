# Relatório — Open Finance 2F: experiência de conexões

Data: 14 de setembro de 2026  
Status: concluída

## Objetivo

A Etapa 2F transforma a infraestrutura Open Finance já existente em uma experiência compreensível na página **Contas**. O usuário não precisa conhecer Item, provider, webhooks ou identificadores externos para conectar, atualizar e usar os dados de demonstração.

## Experiência entregue

- seção Open Finance com identificação discreta de ambiente de demonstração;
- estado vazio orientado para conectar um banco de teste;
- cards de conexão com instituição, estado em linguagem humana, última atualização, quantidade de contas e movimentações;
- estados visuais para conectado, atualizando, atenção necessária, erro e desconectado;
- ação **Atualizar dados**, que consulta o snapshot disponível no provider sem prometer uma nova coleta na instituição;
- feedback de carregamento, sucesso e erro, com prevenção contra envios repetidos;
- contas externas com tipo, saldo e quantidade de movimentações;
- modal responsivo para vincular uma conta bancária a uma conta Nivra existente ou criar uma nova conta Nivra;
- indicação de conta já vinculada e de saldo atualizado pelo banco na listagem principal de contas;
- cartões externos apresentados somente para consulta, pois sua integração ao núcleo de cartões ainda não faz parte desta etapa.

O histórico unificado e a conciliação básica já existentes foram preservados. Os indicadores de origem Manual, Banco e Manual + Banco continuam sendo apresentados nas transações sem alterar regras financeiras.

## Segurança e limites

Nenhuma credencial, token, identificador de Item ou dado de configuração do provider foi adicionado à interface. O React continua recebendo somente o Connect Token temporário necessário para abrir o widget.

Reconexão e desconexão não foram implementadas. O backend atual não possui um fluxo seguro de ponta a ponta para renovar credenciais ou desconectar o Item no provider mantendo corretamente o histórico local. A interface não exibe ações que ainda não funcionam.

O ambiente permanece exclusivamente Sandbox. Nenhum banco real ou credencial de produção foi habilitado.

## Arquivos principais

- `frontend/src/components/finance/OpenFinanceConnectCard.tsx`: experiência de conexão, atualização e vínculo;
- `frontend/src/pages/AccountsPage.tsx`: indicação de conta sincronizada;
- `frontend/src/styles.css`: estilos responsivos e compatíveis com os temas claro e escuro;
- `docs/roadmap.md`: progresso e próxima unidade atualizados;
- `CHANGELOG.md`: registro da entrega.

## Validação

- build React e TypeScript aprovado;
- suíte Python completa aprovada;
- compilação Python aprovada;
- `git diff --check` aprovado;
- validação visual prevista para desktop e larguras mobile de 375 px, 390 px, 430 px e 612 px;
- nenhuma mudança foi feita em schema, regras de saldo, transações, dashboard, autenticação ou webhooks.

## Estado da Etapa 2E

Os webhooks permanecem **implementados e publicados**, mas a validação externa final depende de uma nova entrega real da Pluggy e da repetição do mesmo `eventId`. A Etapa 2F não altera esse estado.

## Próxima tarefa recomendada

**Etapa 2G — Demo para testers.**

Ela deverá preparar um fluxo demonstrável com dados fictícios, estado de erro e instruções de teste. Não faz parte desta entrega.
