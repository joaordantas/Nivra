# Relatório — hardening da autenticação

Data: 12 de setembro de 2026  
Escopo: segurança de conta da Nivra

## Resultado

A autenticação por sessão existente foi preservada e recebeu quatro proteções complementares: verificação de e-mail, troca de senha, recuperação de senha e limites persistentes de tentativa. A revisão final de IDOR/BOLA também cobriu todas as famílias de recursos privados atualmente expostas pela API.

Nenhuma funcionalidade de parcelamento pessoal, recorrência, orçamento, meta, Open Finance, Lumi, notificação ou WhatsApp foi iniciada.

## Verificação de e-mail

- novos cadastros recebem um link válido por 24 horas;
- o token pode ser usado uma única vez;
- um reenvio invalida tokens de verificação anteriores;
- existe intervalo mínimo de 60 segundos entre reenvios;
- usuários antigos continuam acessando a aplicação e recebem um aviso para verificar o endereço;
- o estado de verificação passa a fazer parte de `/api/auth/me`.

O token bruto existe somente no link enviado. O banco armazena SHA-256. O link usa o fragmento `#token=...`, que não é enviado ao servidor quando o navegador abre a página. O React remove o fragmento do histórico antes de enviar o token no corpo protegido por CSRF.

## Recuperação e alteração de senha

O fluxo “Esqueci minha senha” sempre retorna a mesma mensagem, exista ou não uma conta com o e-mail informado. Para contas existentes, o link expira em 30 minutos e é de uso único.

A redefinição bem-sucedida:

- grava uma nova senha bcrypt;
- consome o token;
- revoga outros tokens ativos da conta;
- revoga todas as sessões existentes;
- exige novo login.

A alteração autenticada exige a senha atual, confirmação da nova senha e mantém conectado somente o dispositivo que executou a ação. As outras sessões são encerradas. Novas senhas exigem no mínimo 12 caracteres e no máximo 72 bytes, limite seguro do bcrypt. Senhas antigas continuam aceitas no login para não bloquear usuários já cadastrados.

## Entrega de e-mail

Foi criada uma interface pequena de entrega com duas implementações:

- memória, usada em desenvolvimento e testes;
- Resend por HTTPS, usada em produção.

Não foi adicionada dependência de runtime para o provedor. A implementação usa a API HTTP e pode ser substituída sem alterar os services de autenticação.

Variáveis de produção:

```text
APP_PUBLIC_URL=https://nivra-finance.vercel.app
EMAIL_PROVIDER=resend
RESEND_API_KEY=<chave criada no Resend>
EMAIL_FROM=Nivra <conta@dominio-verificado>
```

Nenhuma credencial foi adicionada ao código ou à documentação.

## Rate limiting

Os eventos ficam no PostgreSQL, compartilhados pelas instâncias serverless. E-mail e endereço de rede não são persistidos em texto; a tabela recebe apenas uma chave SHA-256.

| Operação | Limite básico |
| --- | --- |
| Falhas de login | 8 em 15 minutos por e-mail e endereço de rede |
| Cadastro | 5 por hora por endereço de rede |
| Recuperação de senha | 3 por hora por e-mail e endereço de rede |
| Reenvio de verificação | 5 por hora por usuário, com intervalo de 60 segundos |
| Consumo de link de verificação | 10 em 15 minutos por endereço de rede |
| Consumo de link de recuperação | 10 em 15 minutos por endereço de rede |

Respostas bloqueadas usam HTTP `429` e informam `Retry-After`. Eventos com mais de 24 horas são limpos durante novas gravações.

## Banco e migration

A revisão `b92d8f3a6c10` adiciona:

- `usuarios.email_verificado`;
- `usuarios.email_verificado_em`;
- tabela `auth_tokens`, com finalidade, validade, consumo e revogação;
- tabela `auth_rate_events`, com escopo, chave em hash e data;
- foreign key de tokens para usuários, com exclusão em cascata;
- constraints de finalidade, unicidade de hash e índices de consulta.

Usuários existentes recebem `email_verificado = false` e podem continuar usando o produto. O schema não é criado no startup; a migration deve ser aplicada antes do deploy do código.

## Auditoria IDOR/BOLA

Foram auditadas as rotas e queries de:

- contas e definição de conta principal;
- categorias;
- receitas e despesas;
- transferências;
- cartões;
- faturas e pagamentos;
- compras no cartão;
- vendas e parcelas legadas ainda expostas pela API.

Os IDs do caminho ou do corpo nunca substituem a identidade da sessão. Repositories de entidades privadas filtram também por `usuario_id`, e os services validam relações como conta, categoria, cartão e fatura no contexto do usuário autenticado.

O teste usa dois usuários e tenta ler, editar, excluir ou acionar objetos do outro. Todas as tentativas foram recusadas, e os dados do proprietário permaneceram inalterados.

Durante esta auditoria foram encontrados três usos legados da interface de cursor do SQLite em vendas, parcelas e recebimento de parcela. Eles impediam essas rotas de chegar à verificação de propriedade depois da migração para SQLAlchemy Core. O acesso foi ajustado à interface de conexão atual, sem alterar regra de negócio ou adicionar funcionalidade.

## Interface

Foram adicionados:

- link “Esqueci minha senha” no login;
- página para solicitar recuperação;
- página para definir a nova senha;
- página de confirmação de e-mail;
- aviso discreto de e-mail não verificado na área autenticada;
- item Segurança em Configurações;
- formulário de alteração de senha responsivo.

## Verificações executadas

| Verificação | Resultado |
| --- | --- |
| Compilação de módulos Python | Aprovada |
| Suíte `unittest` | 52 testes aprovados |
| Testes novos de hardening | 7 aprovados |
| Teste novo de IDOR/BOLA | Aprovado |
| Migration completa em banco descartável | Aprovada |
| `alembic current` | `b92d8f3a6c10 (head)` |
| `alembic check` | Nenhuma operação nova detectada |
| Build TypeScript/Vite | Aprovado |
| Verificação de whitespace do diff | Aprovada |

O aviso de depreciação emitido pelo `TestClient` pertence ao pacote de compatibilidade FastAPI/Starlette e não representa falha da aplicação.

## Passos externos obrigatórios

1. Aplicar `alembic upgrade head` no Neon usando a URL direta `DATABASE_URL_UNPOOLED`.
2. Criar ou selecionar um domínio de envio no Resend e concluir os registros DNS de verificação.
3. Criar uma API key restrita ao envio da Nivra.
4. Cadastrar `APP_PUBLIC_URL`, `EMAIL_PROVIDER`, `RESEND_API_KEY` e `EMAIL_FROM` nos ambientes desejados da Vercel.
5. Publicar o commit somente após a migration estar aplicada.
6. Criar uma conta de teste, confirmar o e-mail, recuperar a senha e validar que sessões antigas deixam de funcionar.

Sem a configuração do Resend, cadastro e login continuam funcionando, mas a entrega dos links fica indisponível e o reenvio apresenta uma mensagem amigável. Um domínio próprio verificado é necessário para enviar a usuários externos; o domínio de teste do provedor é adequado apenas para validação inicial restrita.

## Limitações conhecidas

- ainda não existe tela de histórico ou encerramento individual de dispositivos;
- o limite persistente é propositalmente simples e pode ser refinado com métricas e regras globais no trabalho de preparação para produção;
- a resposta genérica impede enumeração direta por conteúdo, mas entrega de e-mail síncrona ainda pode produzir diferença de tempo entre contas existentes e inexistentes;
- a aplicação permanece Alpha e ainda precisa de monitoramento, auditoria operacional, política de privacidade e LGPD antes de dados financeiros críticos.
