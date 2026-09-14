# Teste do Open Finance Sandbox

Este guia permite testar a demonstração de Open Finance da Nivra sem dados bancários reais ou conhecimento técnico do projeto.

## Antes de começar

- Crie a sua própria conta na Nivra em [nivra-finance.vercel.app](https://nivra-finance.vercel.app).
- A demonstração usa somente o ambiente **Sandbox** da Pluggy.
- Nunca informe senhas, dados ou credenciais de um banco real.

## Credenciais fictícias

Ao abrir **Contas → Conectar banco**, escolha **Pluggy Bank** no Connect e use somente estas credenciais oficiais do Sandbox:

| Campo | Valor fictício |
| --- | --- |
| Usuário | `user-ok` |
| Senha | `password-ok` |
| MFA | `123456` |

Esses dados também aparecem na própria tela de Contas, em **Credenciais fictícias do Pluggy Bank**.

## Fluxo principal

1. Crie uma conta Nivra e faça login.
2. Abra **Contas** e localize **Conexões bancárias**.
3. Confirme o selo **Demonstração** e abra as credenciais fictícias, se necessário.
4. Clique em **Conectar banco** e selecione o Pluggy Bank.
5. Conclua o fluxo com as credenciais fictícias acima.
6. Clique em **Atualizar dados** na conexão criada.
7. Confira as contas externas, saldos e quantidade de movimentações importadas.
8. Em uma conta bancária externa, escolha **Vincular à Nivra**.
9. Escolha criar uma conta Nivra ou vincular uma conta manual existente que represente o mesmo dinheiro.
10. Abra **Transações** e **Início** para conferir o histórico e o saldo consolidado.

Cartões externos são apresentados somente para consulta nesta versão. Eles não devem ser vinculados às contas Nivra durante este teste.

## Checklist

- [ ] Criar uma conta Nivra
- [ ] Fazer login
- [ ] Encontrar “Conectar banco” em Contas
- [ ] Entender que é uma demonstração Sandbox
- [ ] Localizar as credenciais fictícias
- [ ] Conectar o Pluggy Bank
- [ ] Atualizar dados
- [ ] Conferir contas, saldo e movimentações
- [ ] Vincular uma conta externa a uma conta Nivra
- [ ] Criar uma conta Nivra pela conexão, se desejar testar esse caminho
- [ ] Atualizar a página sem perder a conexão
- [ ] Sair e entrar novamente
- [ ] Atualizar novamente e confirmar que não há duplicação
- [ ] Testar os temas claro e escuro
- [ ] Testar em celular e desktop
- [ ] Tentar um fluxo incorreto e conferir se a mensagem é compreensível

## Repetir o teste

Não há botão de reset destrutivo. Para repetir uma sincronização, use **Atualizar dados** na conexão já criada: o reprocessamento é idempotente e não deve duplicar dados.

Para testar uma primeira conexão do zero, crie outra conta Nivra. Não reutilize ou compartilhe contas de outros testers.

## Como relatar um problema

Copie e preencha este modelo:

```text
Página:
Ação:
Resultado esperado:
Resultado obtido:
Dispositivo:
Navegador:
Print:
```

Não envie em relatos públicos ou privados:

- senhas pessoais;
- cookies ou tokens;
- Client Secret, API key ou connection string;
- dados bancários reais;
- identificadores técnicos exibidos por ferramentas externas.

O Sandbox não exige nenhum dado bancário real. Se uma tela pedir algo que pareça ser uma credencial real, cancele o fluxo e relate o problema.
