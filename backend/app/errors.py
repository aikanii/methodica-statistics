from fastapi import Request
from fastapi.responses import JSONResponse


FRIENDLY = [
    ("operands could not be broadcast", "The selected variables contain incompatible data types or shapes."),
    ("could not convert", "A value could not be converted to the required numeric type."),
    ("singular matrix", "The model matrix is singular — predictors may be perfectly collinear."),
    ("Perfect separation", "The logistic model has perfect separation; coefficients are not identified."),
    ("not found in the dataset", "A selected column is missing from the working dataset."),
    ("requires exactly 2 groups", "This test needs a grouping variable with exactly two levels."),
    ("binary outcome", "Logistic regression needs an outcome with exactly two categories."),
    ("No complete cases", "After dropping missing values, no rows remained. Impute or select different variables."),
]


def friendly_message(exc: Exception) -> tuple[str, str]:
    raw = str(exc) or exc.__class__.__name__
    for needle, msg in FRIENDLY:
        if needle.lower() in raw.lower():
            return msg, raw
    if "ValueError" in exc.__class__.__name__ or isinstance(exc, ValueError):
        return raw, raw
    return "Analysis could not be completed. See technical details.", raw


def error_payload(title: str, exc: Exception) -> dict:
    user, tech = friendly_message(exc)
    return {
        "error": True,
        "title": title,
        "message": user,
        "technical": tech,
        "type": exc.__class__.__name__,
    }


async def unhandled_handler(request: Request, exc: Exception):
    payload = error_payload("Request failed", exc)
    return JSONResponse(status_code=400, content=payload)
