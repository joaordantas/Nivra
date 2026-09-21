from collections.abc import Callable

from services.insight_service import (
    obter_contexto_financeiro_lumi_service,
    obter_insights_financeiros_service,
)


LUMI_TOOL_CATALOG = {
    "get_financial_insights": {
        "description": "Retorna resumo, comparação, categorias e alertas financeiros do usuário autenticado.",
        "required": ["data_inicio", "data_fim"],
        "read_only": True,
    },
    "get_financial_context": {
        "description": "Retorna o contexto financeiro consolidado e estruturado do usuário autenticado.",
        "required": ["data_inicio", "data_fim"],
        "read_only": True,
    },
}


def executar_lumi_tool(
    tool_name: str,
    arguments: dict,
    usuario_id: int,
    *,
    handlers: dict[str, Callable[..., dict]] | None = None,
) -> dict:
    allowed_handlers = handlers or {
        "get_financial_insights": obter_insights_financeiros_service,
        "get_financial_context": obter_contexto_financeiro_lumi_service,
    }
    handler = allowed_handlers.get(tool_name)
    if handler is None or tool_name not in LUMI_TOOL_CATALOG:
        raise ValueError("Ferramenta da Lumi não permitida.")
    return handler(
        usuario_id,
        str(arguments.get("data_inicio", "")),
        str(arguments.get("data_fim", "")),
    )
