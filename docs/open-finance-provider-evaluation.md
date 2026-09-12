# Avaliação de provider — Open Finance Sandbox

**Decisão:** adotar a **Pluggy** para o MVP de Open Finance em ambiente Sandbox.

Depois da avaliação, a base técnica do provider, o endpoint de Connect Token e o widget React foram implementados. A Nivra ainda não possui credenciais Pluggy configuradas, conexão persistida ou sincronização de dados.

## Por que Pluggy

- Oferece ambiente Sandbox com conector e dados sintéticos, adequado para demonstrar o fluxo sem solicitar credenciais bancárias reais de testers.
- O Pluggy Connect é um widget web que pode ser integrado ao frontend React por meio de um Connect Token temporário.
- O token de integração do frontend tem escopo limitado; as credenciais de aplicação permanecem exclusivamente no FastAPI.
- A API expõe o ciclo necessário para o MVP: item conectado, contas, saldos, transações e webhooks.

## Fluxo proposto

```text
React
  │ solicita um Connect Token autenticado
  ▼
FastAPI
  │ usa credenciais Pluggy somente no servidor
  ▼
Pluggy API
  │ devolve Connect Token temporário
  ▼
React + Pluggy Connect
  │ devolve apenas o identificador externo da conexão
  ▼
FastAPI
  │ sincroniza e persiste dados no PostgreSQL
  ▼
Neon
```

O React nunca receberá `PLUGGY_CLIENT_SECRET`, uma chave de API Pluggy ou uma URL de banco de dados.

## Requisitos confirmados

1. Criar uma aplicação Pluggy e obter `clientId` e `clientSecret` no painel do provider.
2. Guardar essas credenciais somente nas variáveis de ambiente do backend (`PLUGGY_CLIENT_ID` e `PLUGGY_CLIENT_SECRET`).
3. O backend deve obter uma API Key temporária e criar um Connect Token para cada tentativa de conexão; o Connect Token é a única credencial temporária enviada ao navegador.
4. Para o Sandbox, habilitar o conector Sandbox no token/configuração do Connect e usar apenas as credenciais fictícias publicadas pelo provider.
5. Configurar um endpoint HTTPS de webhook quando a etapa de webhooks for implementada.

## Limites da etapa atual

Ainda não é permitido conectar bancos reais. A liberação de produção continua condicionada ao gate separado de Open Finance real, incluindo consentimento, privacidade, segurança, credenciais de produção e testes controlados.

## Fontes oficiais consultadas

- [Autenticação Pluggy](https://docs.pluggy.ai/docs/authentication)
- [Criar Connect Token](https://docs.pluggy.ai/reference/connect-token-create)
- [Integração do Pluggy Connect](https://docs.pluggy.ai/docs/setup-pluggyconnect-widget-on-your-app)
- [Ambientes e Sandbox](https://docs.pluggy.ai/docs/environments-and-configurations)
- [Sandbox](https://docs.pluggy.ai/docs/sandbox)

## Ativação pendente

Criar o ambiente Sandbox da Pluggy e cadastrar as credenciais privadas na Vercel. Consulte o [guia de ativação manual](open-finance-sandbox-setup.md).
