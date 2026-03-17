from types import SimpleNamespace

import application


def test_dashboard_fallback_shows_connect_tenant_link():
    request = SimpleNamespace(session={"user": "Admin", "role": "admin"})
    html = application._dashboard_fallback_html(request, [], 0, 0, 0, "", "")
    assert "Connect M365 Tenant" in html
    assert "href='/tenants'" in html


def test_tenants_fallback_includes_connect_form():
    request = SimpleNamespace(session={"user": "Admin", "role": "admin"})
    html = application._tenants_fallback_html(request, [])
    assert "fallback form" in html
    assert "<form method='post' action='/tenants'" in html
    assert "name='client_secret_ref'" in html
