"""Error classes shared by server/cli/fixture engine.

The real ones live in rmap.engine.errors (pipeline-eng). server.py maps by class NAME as well
so either set works.
"""


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass
