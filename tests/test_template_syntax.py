from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _template_env():
    return Environment(loader=FileSystemLoader("templates"))


def test_all_html_templates_parse():
    env = _template_env()
    for path in Path("templates").glob("*.html"):
        env.get_template(path.name)


def test_dashboard_template_renders_with_minimal_context():
    env = _template_env()
    template = env.get_template("dashboard.html")

    rendered = template.render(
        user="admin",
        role="admin",
        error="",
        tenant_count=0,
        signin_count=0,
        alert_count=0,
        q="",
        can_manage=True,
        is_admin=True,
        alerts=[],
    )

    assert "No alerts found for the current filter." in rendered


def test_tenants_template_renders_with_minimal_context():
    env = _template_env()
    template = env.get_template("tenants.html")

    rendered = template.render(
        user="Admin",
        role="admin",
        tenants=[],
    )

    assert "No tenants configured yet." in rendered
