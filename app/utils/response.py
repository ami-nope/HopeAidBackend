"""app/utils/response.py — Consistent API response helpers."""

from typing import Any



def success_response(data: Any = None, message: str = "Success", status_code: int = 200) -> dict:
    return {"success": True, "data": data, "message": message}


def error_response(error: str, details: Any = None, code: str = None) -> dict:
    return {"success": False, "error": error, "details": details, "code": code}
