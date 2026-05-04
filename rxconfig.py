import os
import reflex as rx

try:
    from reflex_base.plugins.sitemap import SitemapPlugin
    _disable = [SitemapPlugin]
except ImportError:
    _disable = []

_api_url = os.environ.get("API_URL", "http://localhost:8000")
_deploy_url = os.environ.get("DEPLOY_URL", _api_url)

config = rx.Config(
    app_name="brijkillian_stack",
    telemetry_enabled=False,
    backend_host="0.0.0.0",
    backend_port=8000,
    api_url=_api_url,
    deploy_url=_deploy_url,
    disable_plugins=_disable,
)
