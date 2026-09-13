# Ativação do Open Finance Sandbox e webhooks

A integração Sandbox inclui conexão, persistência, sincronização, vínculo com o núcleo e recebimento idempotente de webhooks. As credenciais e o segredo do webhook pertencem exclusivamente ao backend.

## 1. Criar a aplicação Pluggy

1. Acesse o [Dashboard da Pluggy](https://dashboard.pluggy.ai/).
2. Crie a conta ou entre em uma conta existente.
3. Crie uma aplicação de desenvolvimento/Sandbox para a Nivra.
4. Copie o `Client ID` e o `Client Secret`.

Não envie essas credenciais por chat e não as salve em arquivos do repositório.

## 2. Configurar a Vercel

No projeto da Nivra na Vercel, abra **Settings → Environment Variables** e adicione:

```text
PLUGGY_CLIENT_ID=<Client ID da aplicação Sandbox>
PLUGGY_CLIENT_SECRET=<Client Secret da aplicação Sandbox>
PLUGGY_WEBHOOK_SECRET=<segredo aleatório com pelo menos 32 caracteres>
PLUGGY_WEBHOOK_URL=https://nivra-finance.vercel.app/api/open-finance/webhooks/pluggy
```

Use o mesmo `PLUGGY_WEBHOOK_SECRET` ao registrar o webhook na Pluggy. Marque os ambientes em que o Sandbox será testado e faça um novo deploy para que a função FastAPI receba as variáveis.

Não crie variáveis com prefixo `VITE_`: esse prefixo enviaria o valor ao bundle do navegador.

## 3. Aplicar as migrations

Antes do deploy que contém os webhooks, aplique as migrations com a conexão direta do Neon:

```powershell
alembic upgrade head
alembic current
```

O head esperado para a Etapa 2E é `a93c7e4d5f21`.

## 4. Registrar o webhook na Pluggy

O header secreto só pode ser configurado pela API da Pluggy. Com as quatro variáveis abaixo disponíveis apenas no terminal local, execute o utilitário do projeto:

```text
PLUGGY_CLIENT_ID=<Client ID Sandbox>
PLUGGY_CLIENT_SECRET=<Client Secret Sandbox>
PLUGGY_WEBHOOK_SECRET=<o mesmo segredo cadastrado na Vercel>
PLUGGY_WEBHOOK_URL=https://nivra-finance.vercel.app/api/open-finance/webhooks/pluggy
```

```powershell
python scripts/register_pluggy_webhook.py
```

O utilitário cria o webhook `all` ou atualiza o cadastro existente para a URL informada, reativa o registro e envia o segredo em `X-Nivra-Webhook-Secret`. Ele não imprime credenciais.

## 5. Validar o fluxo publicado

1. Entre em `https://nivra-finance.vercel.app`.
2. Abra **Contas**.
3. Selecione **Conectar banco**.
4. Escolha o conector Sandbox/Pluggy Bank.
5. Use somente as credenciais fictícias oficiais:

```text
Usuário: user-ok
Senha: password-ok
MFA, quando solicitado: 123456
```

6. Confirme que o widget mostra sucesso e que a Nivra restaura a conexão.
7. Vincule a conta externa a uma conta Nivra.
8. Sincronize e confirme saldo e transações.
9. No painel da Pluggy, confirme entrega HTTP 200 para os eventos.
10. Reenvie um evento já entregue e confirme que ele aparece como duplicado sem criar outra transação.

O endpoint aceita apenas notificações com o segredo configurado. Falhas temporárias retornam HTTP 503 para permitir as retentativas da Pluggy; requisições sem autenticação são recusadas com HTTP 401.

## Diagnóstico rápido

- Mensagem “Open Finance ainda não foi configurado”: verifique as duas variáveis na Vercel e faça novo deploy.
- Mensagem de credenciais recusadas: gere ou copie novamente as credenciais da aplicação Sandbox.
- Widget não carrega: confirme acesso a `connect.pluggy.ai` no navegador e tente novamente.
- Banco Sandbox não aparece: confirme que o fluxo está com `includeSandbox` habilitado; a Nivra já o habilita nesta versão.
- Webhook retorna 503 de configuração: confirme `PLUGGY_WEBHOOK_SECRET` na Vercel e faça redeploy.
- Webhook retorna 401: atualize o cadastro usando exatamente o mesmo segredo da Vercel.
- Evento não atualiza a Nivra: consulte `eventos_webhook_open_finance` e a página Events da Pluggy pelo `eventId`.
