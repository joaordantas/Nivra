# Ativação manual do Open Finance Sandbox

A base técnica da Etapa 2A está pronta. Para ativar o widget no ambiente publicado, o responsável pelo projeto precisa criar a aplicação Sandbox da Pluggy e cadastrar duas variáveis privadas na Vercel.

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
```

Marque os ambientes em que o Sandbox será testado. Depois, faça um novo deploy para que a função FastAPI receba as variáveis.

Não crie variáveis com prefixo `VITE_`: esse prefixo enviaria o valor ao bundle do navegador.

## 3. Validar o fluxo publicado

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

6. Confirme que o widget mostra sucesso e que a Nivra informa o identificador da conexão Sandbox.

Nesta etapa, a conexão ainda não é persistida no PostgreSQL e contas ou transações ainda não são importadas. Essas entregas pertencem às Etapas 2B e 2C.

## Diagnóstico rápido

- Mensagem “Open Finance ainda não foi configurado”: verifique as duas variáveis na Vercel e faça novo deploy.
- Mensagem de credenciais recusadas: gere ou copie novamente as credenciais da aplicação Sandbox.
- Widget não carrega: confirme acesso a `connect.pluggy.ai` no navegador e tente novamente.
- Banco Sandbox não aparece: confirme que o fluxo está com `includeSandbox` habilitado; a Nivra já o habilita nesta versão.

