import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from repositories.categoria_repo import listar_categorias
from repositories.insight_repo import listar_compras_cartao_periodo
from services.cartao_service import listar_cartoes_formatados, listar_faturas_service
from services.transacao_service import listar_transacoes_formatadas, obter_resumo_financeiro


CARD_WARNING_PERCENT = Decimal("75")
CARD_CRITICAL_PERCENT = Decimal("90")
CARD_CONCENTRATION_PERCENT = Decimal("70")
INVOICE_DUE_SOON_DAYS = 3
TREND_MONTHS = 6
TREND_CHANGE_THRESHOLD_PERCENT = Decimal("5")


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _format_brl(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    formatted = f"{abs(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}R$ {formatted}"


def _percent_change(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None
    return round(float((current - previous) * Decimal("100") / previous), 2)


def _previous_period(start: date, end: date) -> tuple[date, date]:
    if start.day == 1:
        previous_month_end = start - timedelta(days=1)
        previous_start = previous_month_end.replace(day=1)
        previous_day = min(end.day, calendar.monthrange(previous_start.year, previous_start.month)[1])
        return previous_start, previous_start.replace(day=previous_day)
    duration = end - start
    previous_end = start - timedelta(days=1)
    return previous_end - duration, previous_end


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _category_keys(usuario_id: int) -> dict[int, str | None]:
    return {
        int(category_id): str(system_key) if system_key is not None else None
        for category_id, _name, system_key in listar_categorias(usuario_id)
    }


def _card_expenses(usuario_id: int, start: str, end: str) -> list[dict]:
    return [
        {
            "id": int(purchase_id),
            "amount": float(amount),
            "description": str(description),
            "date": str(purchase_date),
            "category_id": int(category_id) if category_id is not None else None,
            "category": str(category_name),
            "category_key": str(category_key) if category_key is not None else None,
            "account": f"Cartão {card_name}",
            "source": "card",
        }
        for (
            purchase_id,
            amount,
            description,
            purchase_date,
            category_id,
            category_name,
            category_key,
            _card_id,
            card_name,
        ) in listar_compras_cartao_periodo(usuario_id, start, end)
    ]


def _period_entries(usuario_id: int, start: str, end: str) -> list[dict]:
    keys = _category_keys(usuario_id)
    entries = [
        {
            "id": int(transaction["id"]),
            "amount": float(transaction["valor"]),
            "description": transaction["comentario"] or transaction["categoria"],
            "date": str(transaction["data"]),
            "type": str(transaction["tipo"]),
            "category_id": transaction["categoria_id"],
            "category": str(transaction["categoria"]),
            "category_key": keys.get(transaction["categoria_id"]),
            "account": str(transaction["conta"]),
            "source": str(transaction["origem"]),
            "neutral": bool(transaction["neutra"]),
        }
        for transaction in listar_transacoes_formatadas(usuario_id, start, end)
    ]
    entries.extend(
        {
            **purchase,
            "type": "saida",
            "neutral": False,
        }
        for purchase in _card_expenses(usuario_id, start, end)
    )
    return entries


def _category_totals(entries: list[dict], transaction_type: str) -> list[dict]:
    filtered = [
        entry for entry in entries
        if entry["type"] == transaction_type and not entry["neutral"]
    ]
    total = sum((_money(entry["amount"]) for entry in filtered), Decimal("0.00"))
    grouped: dict[tuple[int | None, str, str | None], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for entry in filtered:
        key = (entry["category_id"], entry["category"], entry["category_key"])
        grouped[key] += _money(entry["amount"])
    return [
        {
            "category_id": category_id,
            "category": category,
            "category_key": category_key,
            "total": float(value),
            "percentage": round(float(value * Decimal("100") / total), 2) if total else 0.0,
        }
        for (category_id, category, category_key), value in sorted(
            grouped.items(), key=lambda item: item[1], reverse=True
        )
    ]


def _entry_totals(entries: list[dict]) -> dict[str, Decimal]:
    income = sum(
        (_money(item["amount"]) for item in entries if item["type"] == "entrada" and not item["neutral"]),
        Decimal("0.00"),
    )
    expenses = sum(
        (_money(item["amount"]) for item in entries if item["type"] == "saida" and not item["neutral"]),
        Decimal("0.00"),
    )
    return {"income": income, "expenses": expenses, "savings": income - expenses}


def _largest_expenses(entries: list[dict], *, limit: int = 5) -> list[dict]:
    expenses = [
        entry for entry in entries
        if entry["type"] == "saida" and not entry["neutral"]
    ]
    total = sum((_money(entry["amount"]) for entry in expenses), Decimal("0.00"))
    return [
        {
            "id": entry["id"],
            "description": entry["description"],
            "amount": float(_money(entry["amount"])),
            "date": entry["date"],
            "category": entry["category"],
            "account": entry["account"],
            "source": entry["source"],
            "percentage": (
                round(float(_money(entry["amount"]) * Decimal("100") / total), 2)
                if total > 0
                else 0.0
            ),
        }
        for entry in sorted(
            expenses,
            key=lambda item: (_money(item["amount"]), str(item["date"]), int(item["id"])),
            reverse=True,
        )[:limit]
    ]


def _trend_direction(change_percent: float | None) -> str:
    if change_percent is None:
        return "insufficient_data"
    change = _money(change_percent)
    if change >= TREND_CHANGE_THRESHOLD_PERCENT:
        return "up"
    if change <= -TREND_CHANGE_THRESHOLD_PERCENT:
        return "down"
    return "stable"


def _monthly_trend(usuario_id: int, effective_end: date) -> dict:
    anchor_is_month_end = effective_end.day == calendar.monthrange(
        effective_end.year, effective_end.month
    )[1]
    first_month = _shift_month(effective_end.replace(day=1), -(TREND_MONTHS - 1))
    trend_entries = _period_entries(
        usuario_id,
        first_month.isoformat(),
        effective_end.isoformat(),
    )
    points = []
    for offset in range(-(TREND_MONTHS - 1), 1):
        month_reference = _shift_month(effective_end.replace(day=1), offset)
        month_end_day = calendar.monthrange(month_reference.year, month_reference.month)[1]
        cutoff_day = month_end_day if anchor_is_month_end else min(effective_end.day, month_end_day)
        period_start = month_reference.replace(day=1)
        period_end = month_reference.replace(day=cutoff_day)
        totals = _entry_totals([
            entry
            for entry in trend_entries
            if period_start.isoformat() <= str(entry["date"]) <= period_end.isoformat()
        ])
        points.append({
            "month": period_start.strftime("%Y-%m"),
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            **_summary_payload(totals),
        })

    first = points[0]
    last = points[-1]
    expense_change = _percent_change(_money(last["expenses"]), _money(first["expenses"]))
    income_change = _percent_change(_money(last["income"]), _money(first["income"]))
    savings_change = _money(last["savings"]) - _money(first["savings"])
    recent_expenses = [_money(point["expenses"]) for point in points[-3:]]
    sustained_growth = (
        all(value > 0 for value in recent_expenses)
        and recent_expenses[0] < recent_expenses[1] < recent_expenses[2]
        and (
            (recent_expenses[2] - recent_expenses[0])
            * Decimal("100")
            / recent_expenses[0]
        ) >= Decimal("20")
    )
    return {
        "comparison_basis": "full_month" if anchor_is_month_end else "same_day",
        "months_analyzed": TREND_MONTHS,
        "points": points,
        "expense_direction": _trend_direction(expense_change),
        "expense_change_percent": expense_change,
        "income_direction": _trend_direction(income_change),
        "income_change_percent": income_change,
        "savings_direction": (
            "up" if savings_change > 0 else "down" if savings_change < 0 else "stable"
        ),
        "savings_change_amount": float(savings_change),
        "sustained_expense_growth": sustained_growth,
    }


def _summary_payload(values: dict[str, Decimal]) -> dict[str, float]:
    return {key: float(_money(value)) for key, value in values.items()}


def _monthly_projection(
    usuario_id: int,
    requested_start: date,
    requested_end: date,
    effective_end: date,
    current: dict,
) -> dict:
    realized = {
        "income": _money(current["entradas"]),
        "expenses": _money(current["saidas"]),
        "savings": _money(current["saldo"]),
    }
    future_start = max(requested_start, effective_end + timedelta(days=1))
    future_entries = (
        _period_entries(usuario_id, future_start.isoformat(), requested_end.isoformat())
        if future_start <= requested_end
        else []
    )
    known_future = _entry_totals(future_entries)
    projected = {
        key: realized[key] + known_future[key]
        for key in ("income", "expenses", "savings")
    }
    return {
        "as_of": effective_end.isoformat(),
        "realized": _summary_payload(realized),
        "known_future": _summary_payload(known_future),
        "projected": _summary_payload(projected),
        "known_future_entries": len(
            [item for item in future_entries if not item["neutral"]]
        ),
    }


def _card_commitment(usuario_id: int, reference: date) -> dict:
    details = []
    for card in listar_cartoes_formatados(
        usuario_id, incluir_inativos=False, hoje=reference
    ):
        total = max(_money(card["limite_total"]), Decimal("0.00"))
        committed = max(_money(card["limite_utilizado"]), Decimal("0.00"))
        available = max(total - committed, Decimal("0.00"))
        percentage = (
            round(float(committed * Decimal("100") / total), 2)
            if total > 0
            else None
        )
        invoice = card.get("fatura_atual") or {}
        unpaid_invoices = [
            item
            for item in listar_faturas_service(
                int(card["id"]), usuario_id, hoje=reference
            )
            if _money(item["valor_total"]) > 0 and item["status"] != "paga"
        ]
        next_due_invoice = min(
            unpaid_invoices,
            key=lambda item: str(item["data_vencimento"]),
            default=None,
        )
        details.append({
            "card_id": int(card["id"]),
            "name": str(card["nome"]),
            "total_limit": float(total),
            "committed": float(committed),
            "available": float(available),
            "committed_percent": percentage,
            "current_invoice_amount": float(_money(invoice.get("valor_total", 0))),
            "closing_date": str(invoice["data_fechamento"]) if invoice.get("data_fechamento") else None,
            "due_date": str(invoice["data_vencimento"]) if invoice.get("data_vencimento") else None,
            "invoice_status": str(invoice["status"]) if invoice.get("status") else None,
            "next_due_invoice_amount": float(
                _money(next_due_invoice["valor_total"])
                if next_due_invoice is not None
                else Decimal("0.00")
            ),
            "next_due_date": (
                str(next_due_invoice["data_vencimento"])
                if next_due_invoice is not None
                else None
            ),
            "next_due_status": (
                str(next_due_invoice["status"])
                if next_due_invoice is not None
                else None
            ),
        })
    total_limit = sum((_money(item["total_limit"]) for item in details), Decimal("0.00"))
    total_committed = sum((_money(item["committed"]) for item in details), Decimal("0.00"))
    total_available = max(total_limit - total_committed, Decimal("0.00"))
    global_percentage = (
        round(float(total_committed * Decimal("100") / total_limit), 2)
        if total_limit > 0
        else None
    )
    return {
        "total_limit": float(total_limit),
        "total_committed": float(total_committed),
        "total_available": float(total_available),
        "committed_percent": global_percentage,
        "active_cards": len(details),
        "cards": details,
    }


def _unusual_expenses(entries: list[dict]) -> list[dict]:
    expenses = [entry for entry in entries if entry["type"] == "saida" and not entry["neutral"]]
    if len(expenses) < 3:
        return []
    baseline = _money(median(float(entry["amount"]) for entry in expenses))
    if baseline <= 0:
        return []
    threshold = max(Decimal("100.00"), baseline * Decimal("2"))
    return [
        {
            "id": entry["id"],
            "description": entry["description"],
            "amount": entry["amount"],
            "date": entry["date"],
            "category": entry["category"],
            "account": entry["account"],
            "source": entry["source"],
            "baseline": float(baseline),
            "times_baseline": round(float(_money(entry["amount"]) / baseline), 2),
        }
        for entry in sorted(expenses, key=lambda item: _money(item["amount"]), reverse=True)
        if _money(entry["amount"]) >= threshold
    ][:3]


def _attention_items(
    current: dict,
    comparison: dict,
    categories: list[dict],
    unusual: list[dict],
    expense_count: int,
    projection: dict,
    card_commitment: dict,
    trend: dict,
    reference: date,
) -> list[dict]:
    items: list[dict] = []
    expense = _money(current["saidas"])
    income = _money(current["entradas"])
    savings = _money(current["saldo"])

    known_future = projection["known_future"]
    projected = projection["projected"]

    if (
        expense == 0
        and income == 0
        and _money(known_future["income"]) == 0
        and _money(known_future["expenses"]) == 0
        and _money(card_commitment["total_committed"]) == 0
    ):
        items.append({
            "code": "no_activity",
            "severity": "info",
            "title": "Tudo pronto para começar",
            "description": "Registre uma movimentação ou conecte uma conta para receber análises automáticas.",
            "reason": "Não existem receitas ou despesas no período analisado.",
            "action_label": "Adicionar transação",
            "action_path": "/transactions?new=1#new-transaction",
        })

    if savings < 0:
        items.append({
            "code": "negative_savings",
            "severity": "danger",
            "title": "Seus gastos passaram das entradas",
            "description": f"A diferença no período é de {_format_brl(abs(savings))}.",
            "reason": "As despesas registradas são maiores que as receitas.",
            "action_label": "Ver movimentações",
            "action_path": "/transactions",
        })

    if savings >= 0 and _money(projected["savings"]) < 0:
        items.append({
            "code": "known_commitments_negative_projection",
            "severity": "danger",
            "title": "Compromissos conhecidos deixam o mês negativo",
            "description": f"A projeção conhecida termina em {_format_brl(_money(projected['savings']))}.",
            "reason": "O cálculo soma ao realizado somente movimentações futuras já registradas.",
            "action_label": "Ver movimentações",
            "action_path": "/transactions",
        })

    expense_change = comparison["expense_change_percent"]
    if expense_change is not None and expense_change >= 20:
        items.append({
            "code": "expenses_increased",
            "severity": "warning",
            "title": "Seus gastos aumentaram",
            "description": f"Você gastou {expense_change:.0f}% mais que no período anterior.",
            "reason": "A comparação usa períodos equivalentes e ignora transferências internas.",
            "action_label": "Revisar gastos",
            "action_path": "/transactions",
        })

    if trend["sustained_expense_growth"] and not any(
        item["code"] == "expenses_increased" for item in items
    ):
        items.append({
            "code": "sustained_expense_growth",
            "severity": "warning",
            "title": "Seus gastos cresceram por três meses seguidos",
            "description": "A sequência recente mostra aumento contínuo das despesas.",
            "reason": "A regra compara três períodos mensais equivalentes e exige crescimento acumulado de pelo menos 20%.",
            "action_label": "Revisar gastos",
            "action_path": "/transactions",
        })

    if unusual:
        item = unusual[0]
        items.append({
            "code": "unusual_expense",
            "severity": "warning",
            "title": "Um gasto ficou fora do padrão",
            "description": f"{item['description']} foi {item['times_baseline']:.1f}x maior que o gasto típico do período.",
            "reason": "A regra compara o valor com a mediana das despesas e exige ao menos três gastos.",
            "action_label": "Ver movimentações",
            "action_path": "/transactions",
        })

    if categories and expense_count >= 3 and categories[0]["percentage"] >= 40:
        top = categories[0]
        items.append({
            "code": "category_concentration",
            "severity": "info",
            "title": f"{top['category']} concentra seus gastos",
            "description": f"A categoria representa {top['percentage']:.0f}% das despesas do período.",
            "reason": "Concentrações ajudam a identificar onde uma revisão pode ter mais impacto.",
            "action_label": "Filtrar transações",
            "action_path": "/transactions",
        })

    cards = card_commitment["cards"]
    cards_with_percentage = [
        card for card in cards if card["committed_percent"] is not None
    ]
    if cards_with_percentage:
        most_committed = max(
            cards_with_percentage, key=lambda card: card["committed_percent"]
        )
        percentage = _money(most_committed["committed_percent"])
        if percentage >= CARD_CRITICAL_PERCENT:
            items.append({
                "code": "card_limit_critical",
                "severity": "danger",
                "title": f"{most_committed['name']} está com o limite crítico",
                "description": f"{percentage:.0f}% do limite está comprometido e restam {_format_brl(_money(most_committed['available']))}.",
                "reason": "O alerta usa todas as compras de faturas ainda não pagas.",
                "action_label": "Ver cartões",
                "action_path": "/cards",
            })
        elif percentage >= CARD_WARNING_PERCENT:
            items.append({
                "code": "card_limit_warning",
                "severity": "warning",
                "title": f"{most_committed['name']} está próximo do limite",
                "description": f"{percentage:.0f}% do limite já está comprometido.",
                "reason": "O alerta usa todas as compras de faturas ainda não pagas.",
                "action_label": "Ver cartões",
                "action_path": "/cards",
            })

    if len(cards) > 1 and _money(card_commitment["total_committed"]) > 0:
        top_card = max(cards, key=lambda card: _money(card["committed"]))
        concentration = (
            _money(top_card["committed"])
            * Decimal("100")
            / _money(card_commitment["total_committed"])
        )
        if concentration >= CARD_CONCENTRATION_PERCENT:
            items.append({
                "code": "card_commitment_concentration",
                "severity": "info",
                "title": "Seus compromissos estão concentrados em um cartão",
                "description": f"{top_card['name']} reúne {concentration:.0f}% do valor comprometido.",
                "reason": "A concentração compara os valores em aberto dos cartões ativos.",
                "action_label": "Ver cartões",
                "action_path": "/cards",
            })

    unpaid_invoices = [
        card
        for card in cards
        if _money(card["next_due_invoice_amount"]) > 0
        and card["next_due_status"] != "paga"
        and card["next_due_date"] is not None
    ]
    overdue = [card for card in unpaid_invoices if card["next_due_status"] == "vencida"]
    if overdue:
        invoice = min(overdue, key=lambda card: card["next_due_date"])
        items.append({
            "code": "card_invoice_overdue",
            "severity": "danger",
            "title": f"A fatura de {invoice['name']} está vencida",
            "description": f"O valor em aberto é {_format_brl(_money(invoice['next_due_invoice_amount']))}.",
            "reason": "A próxima fatura pendente possui valor em aberto e o vencimento já passou.",
            "action_label": "Ver cartões",
            "action_path": "/cards",
        })
    else:
        due_soon = [
            card
            for card in unpaid_invoices
            if 0 <= (date.fromisoformat(card["next_due_date"]) - reference).days <= INVOICE_DUE_SOON_DAYS
        ]
        if due_soon:
            invoice = min(due_soon, key=lambda card: card["next_due_date"])
            days = (date.fromisoformat(invoice["next_due_date"]) - reference).days
            items.append({
                "code": "card_invoice_due_soon",
                "severity": "warning",
                "title": f"A fatura de {invoice['name']} vence em breve",
                "description": f"{_format_brl(_money(invoice['next_due_invoice_amount']))} vencem em {days} {'dia' if days == 1 else 'dias'}.",
                "reason": f"O vencimento informado pelo cartão está a até {INVOICE_DUE_SOON_DAYS} dias.",
                "action_label": "Ver cartões",
                "action_path": "/cards",
            })

    if savings >= 0 and income > 0:
        rate = savings * Decimal("100") / income
        items.append({
            "code": "positive_savings",
            "severity": "positive",
            "title": "Seu período está positivo",
            "description": f"Você preservou {_format_brl(savings)}, equivalente a {rate:.0f}% das entradas.",
            "reason": "O valor considera receitas menos despesas econômicas do período.",
            "action_label": None,
            "action_path": None,
        })

    priority = {"danger": 0, "warning": 1, "info": 2, "positive": 3}
    return sorted(items, key=lambda item: priority[item["severity"]])[:4]


def obter_insights_financeiros_service(
    usuario_id: int,
    data_inicio: str,
    data_fim: str,
    *,
    hoje: date | None = None,
) -> dict:
    try:
        requested_start = date.fromisoformat(data_inicio)
        requested_end = date.fromisoformat(data_fim)
    except (TypeError, ValueError) as exc:
        raise ValueError("Informe um período válido para os insights.") from exc
    reference = hoje or date.today()
    effective_end = min(requested_end, reference)
    if requested_start > effective_end:
        raise ValueError("A data inicial deve ser anterior ou igual à data final efetiva.")

    previous_start, previous_end = _previous_period(requested_start, effective_end)
    start = requested_start.isoformat()
    end = effective_end.isoformat()
    current = obter_resumo_financeiro(usuario_id, start, end)
    previous = obter_resumo_financeiro(
        usuario_id, previous_start.isoformat(), previous_end.isoformat()
    )
    entries = _period_entries(usuario_id, start, end)
    expense_categories = _category_totals(entries, "saida")
    income_categories = _category_totals(entries, "entrada")
    unusual = _unusual_expenses(entries)
    largest_expenses = _largest_expenses(entries)
    projection = _monthly_projection(
        usuario_id,
        requested_start,
        requested_end,
        effective_end,
        current,
    )
    card_commitment = _card_commitment(usuario_id, reference)
    trend = _monthly_trend(usuario_id, effective_end)
    comparison = {
        "expense_change_amount": float(_money(current["saidas"]) - _money(previous["saidas"])),
        "expense_change_percent": _percent_change(_money(current["saidas"]), _money(previous["saidas"])),
        "income_change_amount": float(_money(current["entradas"]) - _money(previous["entradas"])),
        "income_change_percent": _percent_change(_money(current["entradas"]), _money(previous["entradas"])),
        "savings_change_amount": float(_money(current["saldo"]) - _money(previous["saldo"])),
    }
    expense_count = sum(1 for item in entries if item["type"] == "saida" and not item["neutral"])

    return {
        "period": {
            "start": start,
            "end": end,
            "previous_start": previous_start.isoformat(),
            "previous_end": previous_end.isoformat(),
        },
        "summary": {
            "income": current["entradas"],
            "expenses": current["saidas"],
            "savings": current["saldo"],
        },
        "previous_summary": {
            "income": previous["entradas"],
            "expenses": previous["saidas"],
            "savings": previous["saldo"],
        },
        "comparison": comparison,
        "top_expense_categories": expense_categories[:5],
        "top_income_categories": income_categories[:5],
        "unusual_expenses": unusual,
        "largest_expenses": largest_expenses,
        "monthly_trend": trend,
        "monthly_projection": projection,
        "card_commitment": card_commitment,
        "attention": _attention_items(
            current,
            comparison,
            expense_categories,
            unusual,
            expense_count,
            projection,
            card_commitment,
            trend,
            reference,
        ),
    }


def obter_contexto_financeiro_lumi_service(
    usuario_id: int,
    data_inicio: str,
    data_fim: str,
    *,
    hoje: date | None = None,
) -> dict:
    insights = obter_insights_financeiros_service(
        usuario_id,
        data_inicio,
        data_fim,
        hoje=hoje,
    )
    return {
        "period": insights["period"],
        "financial_position": insights["summary"],
        "comparison": insights["comparison"],
        "monthly_trend": insights["monthly_trend"],
        "largest_expenses": insights["largest_expenses"],
        "top_expense_categories": insights["top_expense_categories"],
        "top_income_categories": insights["top_income_categories"],
        "monthly_projection": insights["monthly_projection"],
        "card_commitment": insights["card_commitment"],
        "attention": insights["attention"],
        "capabilities": {
            "budgets_available": False,
            "goals_available": False,
            "recurrences_available": False,
        },
    }
