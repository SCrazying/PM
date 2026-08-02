"""API v1 路由聚合。"""
from fastapi import APIRouter

from app.api.v1 import auth, m2, m3, nodes, projects, users
from app.core.responses import ok

api_router = APIRouter()


@api_router.get("/ping", tags=["meta"])
def ping():
    return ok({"msg": "pong"})


def _mount(sub_router: APIRouter, prefix: str, tag: str) -> None:
    """把子路由逐条注册到聚合路由（兼容惰性 include 的版本）。"""
    for route in sub_router.routes:
        api_router.add_api_route(
            prefix + route.path,
            route.endpoint,
            methods=list(route.methods),
            name=route.name,
            tags=[tag],
            response_model=getattr(route, "response_model", None),
            dependencies=getattr(route, "dependencies", None) or None,
        )


_mount(auth.router, "/auth", "auth")
_mount(users.router, "/users", "users")
_mount(projects.router, "/projects", "projects")
_mount(nodes.router, "", "nodes/tasks/templates")
_mount(m2.router, "", "m2-progress-report-board")
_mount(m3.router, "", "m3-personal-ai-admin")

