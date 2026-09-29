# Entrega de e-mail da Nivra

Este guia ativa manualmente os e-mails transacionais. Nenhuma credencial deve ser salva no repositório ou exposta com prefixo `VITE_`.

## Resend

1. Crie ou acesse a conta que enviará os e-mails da Nivra.
2. Adicione o domínio de envio e copie os registros DNS solicitados pelo Resend para o provedor do domínio.
3. Aguarde o domínio aparecer como verificado.
4. Crie uma API key restrita ao envio do projeto e guarde-a somente no gerenciador de secrets da Vercel.
5. Escolha um remetente no domínio verificado, por exemplo `Nivra <conta@seu-dominio-verificado.com>`.

## Vercel

Em **Settings → Environment Variables**, configure no ambiente de produção:

```text
APP_ENV=production
EMAIL_PROVIDER=resend
RESEND_API_KEY=<chave privada criada no Resend>
EMAIL_FROM=Nivra <conta@seu-dominio-verificado.com>
APP_PUBLIC_URL=https://seu-dominio-publico.example
```

`APP_PUBLIC_URL` deve conter somente a origem HTTPS pública, sem barra final, caminho, query ou fragmento. A aplicação acrescenta `/verify-email#token=...` ou `/reset-password#token=...` de forma controlada.

Depois de salvar as variáveis, um novo deployment precisa ser iniciado manualmente para recebê-las. Não coloque `RESEND_API_KEY` em `VITE_*`, no frontend, em logs ou em arquivos versionados.

## Gate de entrega real

Use um endereço controlado e execute os dois fluxos:

1. crie uma conta nova;
2. confirme o recebimento do assunto `Confirme seu e-mail na Nivra`;
3. abra o botão ou o link alternativo e confirme a conta verificada;
4. saia da conta e solicite recuperação de senha;
5. confirme o recebimento do assunto `Redefina sua senha da Nivra`;
6. abra o link, defina uma senha nova e confirme que a senha antiga não autentica;
7. entre com a senha nova e confirme que o link não pode ser reutilizado.

O gate só está completamente aprovado quando ambos os e-mails chegam e os dois percursos terminam com sucesso no ambiente publicado.
