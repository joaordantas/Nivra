from datetime import date
from decimal import Decimal

from services.budget_service import normalize_money
from repositories.goal_repo import (
    create_goal, delete_or_archive_goal, find_idempotent_movement, get_goal,
    get_goal_in_connection, goal_transaction, insert_movement, list_goals,
    list_movements, list_movements_in_connection, update_goal,
)


class GoalConflictError(ValueError):
    pass


def _clean(value: str | None, maximum: int, *, required: bool = False) -> str | None:
    cleaned = value.strip() if value else ""
    if required and not cleaned:
        raise ValueError("Informe um nome para a meta.")
    if len(cleaned) > maximum:
        raise ValueError("O texto informado excede o limite permitido.")
    return cleaned or None


def _deadline(value: str | None) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Informe uma data-limite válida.") from exc


def _goal(row: tuple) -> dict:
    goal_id, _user, name, description, target, deadline, status, created, updated, saved = row
    target_d = normalize_money(target)
    saved_d = Decimal(str(saved)).quantize(Decimal("0.01"))
    remaining = max(target_d - saved_d, Decimal("0.00"))
    progress = (saved_d * Decimal("100") / target_d).quantize(Decimal("0.01"))
    return {"id": int(goal_id), "name": str(name), "description": description, "target_amount": target_d,
            "saved_amount": saved_d, "remaining_amount": remaining, "progress_percentage": progress,
            "deadline": str(deadline)[:10] if deadline else None, "lifecycle_status": str(status),
            "completed": saved_d >= target_d, "created_at": str(created), "updated_at": str(updated)}


def create_goal_service(user_id: int, name: str, description: str | None, target: object, deadline: str | None, *, today: date | None = None) -> dict:
    goal_id = create_goal(user_id, _clean(name, 120, required=True), _clean(description, 600), normalize_money(target), _deadline(deadline))
    return get_goal_service(goal_id, user_id, today=today)


def list_goals_service(user_id: int, *, include_archived: bool = True, today: date | None = None) -> list[dict]:
    return [_goal(row) for row in list_goals(user_id, today or date.today(), include_archived)]


def get_goal_service(goal_id: int, user_id: int, *, today: date | None = None) -> dict:
    row = get_goal(goal_id, user_id, today or date.today())
    if row is None:
        raise LookupError("Meta não encontrada.")
    return _goal(row)


def update_goal_service(goal_id: int, user_id: int, changes: dict, *, today: date | None = None) -> dict:
    current = get_goal(goal_id, user_id, today or date.today())
    if current is None:
        raise LookupError("Meta não encontrada.")
    name = _clean(changes.get("name", current[2]), 120, required=True)
    description = _clean(changes.get("description", current[3]), 600)
    target = normalize_money(changes.get("target_amount", current[4]))
    deadline = _deadline(changes["deadline"]) if "deadline" in changes else (date.fromisoformat(str(current[5])[:10]) if current[5] else None)
    status = changes.get("lifecycle_status", current[6])
    if status not in {"active", "archived"}:
        raise ValueError("Estado da meta inválido.")
    update_goal(goal_id, user_id, name, description, target, deadline, status)
    return get_goal_service(goal_id, user_id, today=today)


def delete_goal_service(goal_id: int, user_id: int) -> str:
    outcome = delete_or_archive_goal(goal_id, user_id)
    if outcome is None:
        raise LookupError("Meta não encontrada.")
    return outcome


def _movement(row: tuple, today: date) -> dict:
    movement_id, goal_id, kind, amount, effective, description, key, created = row
    return {"id": int(movement_id), "goal_id": int(goal_id), "type": str(kind), "amount": normalize_money(amount),
            "effective_date": str(effective)[:10], "description": description, "idempotency_key": key,
            "effective": date.fromisoformat(str(effective)[:10]) <= today, "created_at": str(created)}


def list_goal_movements_service(goal_id: int, user_id: int, *, today: date | None = None) -> list[dict]:
    get_goal_service(goal_id, user_id, today=today)
    reference = today or date.today()
    return [_movement(row, reference) for row in list_movements(goal_id, user_id)]


def add_goal_movement_service(user_id: int, goal_id: int, kind: str, amount_value: object, effective_value: str, description: str | None, idempotency_key: str | None, *, today: date | None = None) -> dict:
    if kind not in {"contribution", "withdrawal"}:
        raise ValueError("Tipo de movimentação inválido.")
    amount = normalize_money(amount_value)
    try:
        effective = date.fromisoformat(effective_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Informe uma data efetiva válida.") from exc
    description = _clean(description, 300)
    key = idempotency_key.strip() if idempotency_key else None
    reference = today or date.today()
    with goal_transaction(goal_id, user_id) as conn:
        goal = get_goal_in_connection(conn, goal_id, user_id)
        if goal is None:
            raise LookupError("Meta não encontrada.")
        if goal[6] != "active":
            raise GoalConflictError("Reative a meta antes de registrar movimentações.")
        if key:
            existing = find_idempotent_movement(conn, user_id, key)
            if existing is not None:
                same = int(existing[1]) == goal_id and existing[2] == kind and normalize_money(existing[3]) == amount and str(existing[4])[:10] == effective.isoformat() and (existing[5] or None) == description
                if not same:
                    raise GoalConflictError("A chave de idempotência já foi utilizada.")
                return _movement(existing, reference)
        movements = list_movements_in_connection(conn, goal_id, user_id)
        timeline = [(date.fromisoformat(str(row[4])[:10]), int(row[0]), Decimal(str(row[3])) if row[2] == "contribution" else -Decimal(str(row[3]))) for row in movements]
        timeline.append((effective, 2**63 - 1, amount if kind == "contribution" else -amount))
        balance = Decimal("0.00")
        for _day, _order, delta in sorted(timeline):
            balance += delta
            if balance < 0:
                raise GoalConflictError("A retirada deixaria o valor reservado negativo.")
        movement_id = insert_movement(conn, goal_id, user_id, kind, amount, effective, description, key)
        created = next(row for row in list_movements_in_connection(conn, goal_id, user_id) if int(row[0]) == movement_id)
        return _movement(created, reference)
