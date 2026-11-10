import importlib


def test_app_modules_importable():
    """Valida que todos os módulos principais de app/ podem ser importados sem erro."""
    modules = [
        "app.main",
        "app.api.webhook",
        "app.core.memory",
        "app.agent.memory",
        "app.modules.scheduler",
        "app.modules.scheduler.config",
        "app.modules.scheduler.service",
        "app.modules.scheduler.runner",
        "app.integrations.evolution",
        "app.integrations.evolution.client",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None


def test_webhook_route_registered_in_main_app():
    """Valida que a rota POST /webhook está registrada na instância FastAPI app.main:app."""
    from app.api.webhook import router as webhook_router
    from app.main import app

    router_routes = [
        (route.path, tuple(sorted(route.methods)))
        for route in webhook_router.routes
        if hasattr(route, "path") and hasattr(route, "methods")
    ]
    assert any(path == "/webhook" and "POST" in methods for path, methods in router_routes)

    openapi_paths = app.openapi().get("paths", {})
    assert "/webhook" in openapi_paths
    assert "post" in openapi_paths["/webhook"]
