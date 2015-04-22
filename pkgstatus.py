import datetime
import json
from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from flask.ext.pymongo import PyMongo
import flask.ext.pymongo as pymongo
import os
import time

def create_app():
    app = Flask(__name__)
    Bootstrap(app)
    mongo = PyMongo(app)

    @app.template_filter('duration')
    def duration_filter(s):
        s = int(s)
        hours, remainder = divmod(s, 3600)
        minutes, seconds = divmod(remainder, 60)
        return '%d:%02d:%02d' % (hours, minutes, seconds)

    @app.template_filter('datetime')
    def format_datetime(timestamp, format='%Y-%m-%d %H:%M'):
        date = datetime.datetime.fromtimestamp(int(timestamp))
        return time.strftime(format, time.gmtime(int(timestamp)))

    def get_builds(selector):
        return mongo.db.builds.find(selector).sort([
            ('setname', pymongo.ASCENDING),
            ('ptname', pymongo.ASCENDING),
            ('jailname', pymongo.ASCENDING),
            ('buildname', pymongo.ASCENDING),
            ])

    @app.route('/')
    def index():
        build_types = ["package", "qat", "exp"]
        latest_builds = {}
        for build_type in build_types:
            latest_builds[build_type] = get_builds({"latest": True,
                "type": build_type})
        server_map = {x["_id"]:x for x in
                list(mongo.db.servers.find())}
        return render_template('index.html',
                build_types=build_types,
                latest_builds=latest_builds,
                servers=server_map)

    return app

if __name__ == "__main__":
    create_app().run(debug=True, host='0.0.0.0')
