# Relatório — Open Finance Etapa 2A

## Resultado

A Nivra agora possui a base técnica para abrir o Pluggy Connect em modo Sandbox. A aplicação Pluggy de desenvolvimento e as credenciais privadas na Vercel foram confirmadas. A validação final depende somente da conexão de uma instituição fictícia em uma sessão autenticada da Nivra.

## Backend

- criada uma abstração de provider para evitar acoplamento das regras da Nivra à Pluggy;
- implementada autenticação server-side na API da Pluggy;
- implementado cache em memória da API Key por instância serverless;
- criado Connect Token individual com referência interna do usuário e `avoidDuplicates`;
- criado `POST /api/open-finance/connect-token`;
- endpoint protegido por sessão autenticada e CSRF;
- erros do provider são convertidos em mensagens seguras, sem retornar credenciais ou respostas internas.

## Frontend

- adicionada a dependência oficial `react-pluggy-connect`;
- criado card de conexão na página de Contas;
- widget configurado em português, para o Brasil, com tema claro/escuro e Sandbox habilitado;
- adicionados estados de preparação, erro, sucesso e fechamento;
- layout adaptado para celular;
- o frontend recebe somente o Connect Token temporário.

## Configuração

- adicionadas `PLUGGY_CLIENT_ID` e `PLUGGY_CLIENT_SECRET` ao `.env.example`;
- nenhuma credencial real foi adicionada ao projeto;
- não existe variável Pluggy com prefixo `VITE_`.

## Testes e verificações

- 5 testes específicos do provider e endpoint: aprovados;
- suíte completa: 57 testes aprovados;
- compilação Python: aprovada;
- build React/TypeScript: aprovado;
- auditoria das dependências de produção: nenhuma vulnerabilidade encontrada;
- busca de secrets: aprovada.

## Limitações desta etapa

- o fluxo real ainda precisa ser validado em uma sessão autenticada da Nivra;
- o `itemId` ainda não é persistido;
- contas, saldos e transações ainda não são importados;
- webhooks e conciliação pertencem a etapas posteriores.

Consulte [Ativação manual do Sandbox](open-finance-sandbox-setup.md) para concluir os passos externos.

## Validação externa parcial

- aplicação `Nivra Development` confirmada no ambiente de desenvolvimento da Pluggy;
- `PLUGGY_CLIENT_ID` e `PLUGGY_CLIENT_SECRET` confirmadas como secrets de Produção na Vercel, sem leitura ou registro dos valores;
- commit `f4a8de9` publicado no GitHub;
- deployment de Produção confirmado como `Ready`;
- `GET /api/health` respondeu HTTP 200 com banco online;
- conexão do Pluggy Bank ainda pendente em uma sessão autenticada.
