from jinja2 import Environment, FileSystemLoader


def test_dashboard_template_parses():
    env = Environment(loader=FileSystemLoader("templates"))
    env.get_template("dashboard.html")
