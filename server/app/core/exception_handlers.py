import re
from typing import cast
from fastapi import Request, status, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    DataError,
)
from app.logging_config import logger


def parse_db_error_detail(detail: str) -> str:
    """
    Dynamically parse DB error details (Postgres and SQLite) into human-friendly messages.
    """
    if not detail:
        return ""

    # 1. Postgres Unique Constraints: Key (col1, col2)=(val1, val2) already exists
    unique_match = re.search(r"Key \((.*?)\)=\((.*?)\) already exists", detail)
    if unique_match:
        fields_raw, values_raw = unique_match.groups()
        fields = [f.strip() for f in fields_raw.split(",")]
        values = [v.strip().strip('"').strip("'") for v in values_raw.split(",")]

        display_pairs = []
        for f, v in zip(fields, values):
            if not f.endswith("_id"):
                label = f.replace("_", " ").title()
                display_pairs.append(f'{label} "{v}"')

        if not display_pairs:
            return "A record with this information already exists."

        return f"{' and '.join(display_pairs)} already exists."

    # 2. Postgres Foreign Key Constraints: Key (id)=(...) is still referenced from table "table_name"
    fk_match = re.search(
        r"Key \((.*?)\)=\((.*?)\) is still referenced from table \"(.*?)\"", detail
    )
    if fk_match:
        _, _, table = fk_match.groups()
        table_label = table.replace("_", " ").title()
        return f"This record is still used in {table_label} and cannot be deleted."

    return ""


async def http_exception_handler(request: Request, exc: Exception):
    """Handle FastAPI / Starlette HTTPExceptions."""
    http_exc = cast(HTTPException, exc)

    headers = getattr(http_exc, "headers", None)
    return JSONResponse(
        status_code=http_exc.status_code,
        content={
            "detail": http_exc.detail,
            "error": http_exc.detail,
        },
        headers=headers,
    )


async def request_validation_error_handler(request: Request, exc: Exception):
    """Handle FastAPI request validation errors."""
    req_exc = cast(RequestValidationError, exc)

    errors = []
    for error in req_exc.errors():
        loc = error.get("loc", [])
        field = str(loc[-1]) if loc else "field"
        msg = error.get("msg", "invalid value")

        # Clean up common Pydantic messages
        msg = msg.replace("Value error, ", "").replace("Assertion failed, ", "")
        errors.append(f"{field.replace('_', ' ').title()}: {msg}")

    message = ", ".join(errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": message,
            "error": message,
        },
    )


async def pydantic_validation_error_handler(request: Request, exc: Exception):
    """Handle internal Pydantic validation errors with clean messaging."""
    val_exc = cast(ValidationError, exc)

    error_msgs = []
    for err in val_exc.errors():
        loc = err.get("loc", [])
        field = str(loc[-1]) if loc else ""
        msg = err.get("msg", "Invalid value")

        msg = msg.split("[type=")[0].strip()
        msg = msg.replace("Value error, ", "").replace("Assertion failed, ", "")

        if field:
            error_msgs.append(f"{field.replace('_', ' ').title()}: {msg}")
        else:
            error_msgs.append(msg)

    message = ", ".join(error_msgs) if error_msgs else "Validation error"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": message,
            "error": message,
        },
    )


async def integrity_error_handler(request: Request, exc: Exception):
    """Handle database unique constraints, foreign keys and integrity violations."""
    logger.error(f"Database integrity error: {exc}")

    orig = getattr(exc, "orig", None)
    detail = getattr(orig, "detail", None) if orig else None

    if not detail:
        detail = str(orig) if orig else str(exc)

    message = parse_db_error_detail(detail)

    if not message:
        # Fallback parsing for general/SQLite DB constraint errors
        error_msg_lower = str(exc).lower()
        if "unique constraint" in error_msg_lower or "duplicate" in error_msg_lower:
            message = "A record with this information already exists."
        elif (
            "foreign key constraint" in error_msg_lower
            or "foreignkey" in error_msg_lower
        ):
            message = "Referenced record does not exist or is still in use."
        elif "not null constraint" in error_msg_lower or "not-null" in error_msg_lower:
            message = "A required field is missing."
        else:
            message = "Database integrity violation."

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": message,
            "error": message,
        },
    )


async def operational_error_handler(request: Request, exc: Exception):
    """Handle database connectivity issues."""
    logger.error(f"Database operational error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Database service is temporarily unavailable.",
            "error": "Database service is temporarily unavailable.",
        },
    )


async def data_error_handler(request: Request, exc: Exception):
    """Handle invalid DB formats or types."""
    logger.error(f"Database data error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Invalid format or data type for database operation.",
            "error": "Invalid format or data type for database operation.",
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled exceptions to prevent exposing raw tracebacks."""
    logger.error(f"Unhandled system exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "error": str(exc),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI application."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(DataError, data_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
