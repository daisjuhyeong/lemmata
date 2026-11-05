"""Errors the server maps to HTTP status codes (NotFound -> 404, BadRequest -> 400)."""


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass
