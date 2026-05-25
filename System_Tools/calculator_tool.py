from __future__ import annotations

import ast
import operator
import re
from typing import Any


class CalculatorTool:
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "local_ready", "service_id": "local_compute"}

    def supported_actions(self) -> list[str]:
        return ["calculate", "convert_units", "estimate_budget", "date_math", "compare_numbers"]

    def calculate(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        expression = self._extract_expression(tool_intent.normalized_text)
        if dry_run:
            return {
                "ok": True,
                "status": "dry_run",
                "summary": f"Would calculate: {expression}",
                "data": {"expression": expression},
            }

        try:
            result = self._safe_eval(expression)
        except Exception as exc:
            return {
                "ok": False,
                "status": "error",
                "summary": "Calculator could not evaluate the expression.",
                "data": {"expression": expression},
                "error": str(exc),
            }

        return {
            "ok": True,
            "status": "completed",
            "summary": f"{expression} = {result}",
            "data": {"expression": expression, "result": result},
        }

    def convert_units(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_implemented(tool_intent, dry_run, "Unit conversion")

    def estimate_budget(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_implemented(tool_intent, dry_run, "Budget estimation")

    def date_math(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_implemented(tool_intent, dry_run, "Date math")

    def compare_numbers(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_implemented(tool_intent, dry_run, "Number comparison")

    def _extract_expression(self, text: str) -> str:
        expression = text
        expression = expression.replace("percent of", "/100*")
        expression = expression.replace("percent", "/100")
        expression = expression.replace("plus", "+")
        expression = expression.replace("minus", "-")
        expression = expression.replace("times", "*")
        expression = expression.replace("multiplied by", "*")
        expression = expression.replace("divided by", "/")
        expression = expression.replace("what is", "")
        expression = expression.replace("what s", "")
        expression = re.sub(r"[^0-9+\-*/().\s]", " ", expression)
        expression = re.sub(r"\s+", " ", expression).strip()
        if not expression:
            raise ValueError("No numeric expression found.")
        return expression

    def _safe_eval(self, expression: str) -> float | int:
        node = ast.parse(expression, mode="eval").body
        return self._eval_node(node)

    def _eval_node(self, node: ast.AST) -> float | int:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self.OPERATORS:
            return self.OPERATORS[type(node.op)](self._eval_node(node.left), self._eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in self.OPERATORS:
            return self.OPERATORS[type(node.op)](self._eval_node(node.operand))
        raise ValueError("Unsupported calculator expression.")

    def _not_implemented(self, tool_intent: Any, dry_run: bool, label: str) -> dict[str, Any]:
        status = "dry_run" if dry_run else "not_implemented"
        return {
            "ok": dry_run,
            "status": status,
            "summary": f"{label} is not implemented yet.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
