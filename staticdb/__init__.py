"""A site to add an API to static sites."""

import contextlib
import datetime
import functools
import sqlite3
import uuid
from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode

import jinja2
import sqlalchemy
from databases import Database
from starlette.applications import Starlette
from starlette.datastructures import ImmutableMultiDict
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

_ENV = jinja2.Environment(
    autoescape=True,
    loader=jinja2.FileSystemLoader("templates"),
    lstrip_blocks=True,
    trim_blocks=True,
)
_TEMPLATES = Jinja2Templates(env=_ENV)


class _DictType(sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.String

    def process_bind_param(self, value, dialect: sqlalchemy.Dialect) -> str:
        assert isinstance(value, ImmutableMultiDict)
        assert all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in value.multi_items()
        )
        return urlencode(value.multi_items())

    def process_result_value(
        self, value, dialect: sqlalchemy.Dialect
    ) -> ImmutableMultiDict[str, str]:
        assert isinstance(value, str)
        return ImmutableMultiDict(parse_qsl(value, keep_blank_values=True))


_METADATA = sqlalchemy.MetaData()
_API = sqlalchemy.Table(
    "api",
    _METADATA,
    sqlalchemy.Column("id", sqlalchemy.Uuid, nullable=False, primary_key=True),
)
_API_DATA = sqlalchemy.Table(
    "api_data",
    _METADATA,
    sqlalchemy.Column(
        "id", sqlalchemy.Integer, nullable=False, primary_key=True, autoincrement=True
    ),
    sqlalchemy.Column("api", sqlalchemy.Uuid, nullable=False),
    sqlalchemy.Column("time", sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column("data", _DictType, nullable=False),
)
_DATABASE = Database("sqlite+aiosqlite:///db.sqlite3")


@contextlib.asynccontextmanager
async def _lifespan(app: Starlette):
    async with _DATABASE:
        yield


def _msg(request: Request, msg: str, status_code: int = 200) -> Response:
    if "text/html" in request.headers.get("Accept", ""):
        return _TEMPLATES.TemplateResponse(
            request, "msg.html", {"msg": msg}, status_code=status_code
        )
    return Response(msg, status_code, media_type="text/plain")


def _index(request: Request) -> Response:
    return _msg(request, "Welcome!")


async def _create(request: Request) -> Response:
    while True:
        api_id = uuid.uuid4()
        with contextlib.suppress(sqlite3.IntegrityError):
            await _DATABASE.execute(_API.insert().values(id=api_id))
            break
    return _msg(request, f"Success! ID: {api_id}")


async def _is_api(request: Request) -> bool:
    return bool(
        await _DATABASE.fetch_one(
            _API.select().where(_API.c.id == request.path_params["api_id"])
        )
    )


class _Column(NamedTuple):
    name: str
    size: int


async def _show(request: Request) -> Response:
    if not await _is_api(request):
        return _msg(request, "API not found", 404)

    data = await _DATABASE.fetch_all(
        _API_DATA.select().where(_API_DATA.c.api == request.path_params["api_id"])
    )
    column_keys = functools.reduce(lambda x, y: x.union(y["data"].keys()), data, set())
    columns = [
        _Column(
            name=key,
            size=max(len(row["data"].getlist(key)) for row in data),
        )
        for key in sorted(column_keys)
    ]

    return _TEMPLATES.TemplateResponse(
        request, "show.html", {"data": data, "columns": columns}
    )


async def _api(request: Request) -> Response:
    """Store data from api request."""
    if not await _is_api(request):
        return _msg(request, "API not found", 404)

    if request.method == "GET":
        data = request.query_params
    elif request.method == "POST":
        async with request.form() as form:
            data = ImmutableMultiDict(
                (key, value)
                for key, value in form.multi_items()
                if isinstance(key, str)
            )
    else:
        assert False

    await _DATABASE.execute(
        _API_DATA.insert().values(
            api=request.path_params["api_id"],
            time=datetime.datetime.now(tz=datetime.UTC),
            data=data,
        )
    )

    return _msg(request, "Success!")


app = Starlette(
    routes=[
        Route("/", endpoint=_index),
        Route("/create", endpoint=_create),
        Route("/show/{api_id:uuid}", endpoint=_show),
        Route("/api/{api_id:uuid}", endpoint=_api, methods=["GET", "POST"]),
    ],
    lifespan=_lifespan,
)
