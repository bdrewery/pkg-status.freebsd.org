from pkgstatus import create_app
from flask.cli import FlaskGroup
from flask import url_for
import urllib.parse

app = create_app()

cli = FlaskGroup(app)

@cli.command("list_routes")
def list_routes():
    output = []
    for rule in app.url_map.iter_rules():
        options = {}
        for arg in rule.arguments:
            options[arg] = "[{0}]".format(arg)

        methods = ','.join(rule.methods)
        url = url_for(rule.endpoint, **options)
        line = urllib.parse.unquote("{:50s} {:20s} {}".format(rule.endpoint, methods, url))
        output.append(line)

    for line in sorted(output):
        print(line)

if __name__ == "__main__":
    cli()
