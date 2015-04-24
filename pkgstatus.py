import datetime
import json
from flask import Flask, render_template, request
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
        return {'filter': selector,
                'results': list(mongo.db.builds.find(selector).sort([
                    ('snap.now - snap.elapsed', pymongo.DESCENDING),
                    ('setname', pymongo.ASCENDING),
                    ('ptname', pymongo.ASCENDING),
                    ('jailname', pymongo.ASCENDING),
                    ('buildname', pymongo.ASCENDING),
                    ]))}

    # Mongo does not allow '.' in keys due to dot-notation.
    def fix_port_origins(ports):
        if 'pkgnames' not in ports:
            return
        for origin in ports['pkgnames']:
            if '%' in origin:
                fixed_origin = origin.replace('%', '.')
                ports['pkgnames'][fixed_origin] = ports['pkgnames'].pop(origin)
                for field in ['built', 'failed', 'skipped', 'ignored']:
                    if origin in ports[field]:
                        ports[field][fixed_origin] = ports[field].pop(origin)

    def get_server_map():
        return {x["_id"]:x for x in list(mongo.db.servers.find())}

    @app.route('/')
    def index():
        build_types = ["package", "qat", "exp"]
        latest_builds = {}
        for build_type in build_types:
            latest_builds[build_type] = get_builds({"latest": True,
                "type": build_type})
        return render_template('index.html',
                latest=True,
                build_types=build_types,
                latest_builds=latest_builds,
                servers=get_server_map())

    @app.route('/builds')
    def builds():
        query = {}
        for key, value in request.args.iteritems():
            query[key] = value
        if "setname" in query:
            if query['setname'] == "default":
                query['setname'] = ''
        if "all" in query:
            del(query['all'])
            latest = False
        else:
            query['latest'] = True
            latest = True
        if "build_types" in query:
            build_types = query['build_types']
        else:
            build_types = ["package", "qat", "exp"]
        latest_builds = {}
        for build_type in build_types:
            query['type'] = build_type
            latest_builds[build_type] = get_builds(query)
        return render_template('index.html',
                latest=latest,
                servers=get_server_map(),
                build_types=build_types,
                latest_builds=latest_builds)

    @app.route('/builds/<buildid>')
    def build(buildid):
        build = mongo.db.builds.find_one_or_404({'_id': buildid})
        ports = mongo.db.ports.find_one({'_id': buildid})
        fix_port_origins(ports)
        return render_template('build.html',
                build=build,
                ports=ports,
                servers=get_server_map())

    return app

if __name__ == "__main__":
    create_app().run(debug=True, host='0.0.0.0')
