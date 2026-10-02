"""Create or remove the fictional P7.2 visual dataset in APP_ENV=test only."""

from __future__ import annotations

import argparse
import os

from database.connection import get_connection
from services.notification_service import notification_service
from services.notification_types import NotificationSeverity, NotificationType


def require_test_environment() -> None:
    if os.environ.get("APP_ENV", "").strip().casefold() != "test":
        raise RuntimeError("O dataset visual P7.2 so pode ser usado com APP_ENV=test.")


def user_id_for_email(email: str) -> int:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id FROM usuarios WHERE lower(email) = lower(?)",
            (email,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("Usuario de teste nao encontrado.")
    return int(row[0])


def remove_dataset(user_id: int) -> int:
    connection = get_connection()
    try:
        result = connection.execute(
            "DELETE FROM notifications WHERE usuario_id = ? AND chave_dedupe LIKE ?",
            (user_id, "p72-demo:%"),
        )
        connection.commit()
        return result.rowcount
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def seed_dataset(user_id: int) -> int:
    long_title = ("Título longo para validar quebra de linha e leitura confortável no centro de notificações. " * 3)[:160]
    long_message = (
        "Mensagem fictícia extensa para validar largura, quebra de palavras, rolagem e legibilidade em telas pequenas. "
        "Nenhum valor financeiro real ou dado sensível faz parte deste conteúdo. " * 5
    )[:600]
    fixtures = [
        (NotificationType.SYSTEM, NotificationSeverity.INFO, "Bem-vindo ao centro de notificações", "Este é um evento interno fictício para validar a experiência."),
        (NotificationType.FINANCIAL_ALERT, NotificationSeverity.WARNING, "Revisão financeira fictícia", "Uma informação de teste precisa da sua atenção, sem alterar seus dados."),
        (NotificationType.CARD_ALERT, NotificationSeverity.CRITICAL, "Alerta importante de cartão fictício", "Exemplo visual de prioridade crítica, sem cobrança ou fatura real."),
        (NotificationType.BUDGET_ALERT, NotificationSeverity.WARNING, "Orçamento de demonstração", "Notificação visual; alertas reais serão conectados somente na P7.3."),
        (NotificationType.GOAL_ALERT, NotificationSeverity.INFO, "Meta fictícia atualizada", "Exemplo de apresentação para metas futuras."),
        (NotificationType.SUMMARY, NotificationSeverity.INFO, "Resumo de demonstração", "Exemplo de resumo interno sem dados financeiros."),
        (NotificationType.SYSTEM, NotificationSeverity.INFO, long_title, long_message),
        (NotificationType.FINANCIAL_ALERT, NotificationSeverity.INFO, "Movimento de teste 1", "Item fictício para paginação."),
        (NotificationType.CARD_ALERT, NotificationSeverity.WARNING, "Movimento de teste 2", "Item fictício para paginação."),
        (NotificationType.BUDGET_ALERT, NotificationSeverity.INFO, "Movimento de teste 3", "Item fictício para paginação."),
        (NotificationType.GOAL_ALERT, NotificationSeverity.WARNING, "Movimento de teste 4", "Item fictício para paginação."),
        (NotificationType.SUMMARY, NotificationSeverity.INFO, "Movimento de teste 5", "Item fictício para paginação."),
        (NotificationType.SYSTEM, NotificationSeverity.INFO, "Movimento de teste 6", "Item fictício para paginação."),
        (NotificationType.FINANCIAL_ALERT, NotificationSeverity.WARNING, "Movimento de teste 7", "Item fictício para paginação."),
    ]
    created = []
    for index, (notification_type, severity, title, message) in enumerate(fixtures, start=1):
        created.append(notification_service.notify(
            user_id,
            notification_type,
            title,
            message,
            severity=severity,
            metadata={"source_type": "p72_visual_test", "source_id": str(index)},
            dedupe_key=f"p72-demo:{index}",
        ))
    for notification in created[-3:]:
        notification_service.mark_read(user_id, notification["id"])
    return len(created)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dataset visual ficticio da P7.2")
    parser.add_argument("--email", required=True, help="Conta existente no banco de teste")
    parser.add_argument("--remove", action="store_true", help="Remove somente notificacoes p72-demo")
    args = parser.parse_args()
    require_test_environment()
    user_id = user_id_for_email(args.email)
    count = remove_dataset(user_id) if args.remove else seed_dataset(user_id)
    action = "removidas" if args.remove else "preparadas"
    print(f"Notificacoes ficticias {action}: {count}.")


if __name__ == "__main__":
    main()
