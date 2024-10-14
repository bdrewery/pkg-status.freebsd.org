import datetime
import json
from flask import Flask, jsonify, render_template, request, make_response, url_for
from flask_bootstrap import Bootstrap5
from flask_jsglue import JSGlue
from flask_pymongo import PyMongo
from urllib.parse import urlencode
import flask_pymongo as pymongo
import os
import time

def create_app():
    app = Flask(__name__, static_folder='public/static', static_url_path='/static')
    app.config['APPLICATION_ROOT'] = '/'
    app.config['PREFERRED_URL_SCHEME'] = 'http'
    app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/pkgstatus')

    Bootstrap5(app)
    jsglue = JSGlue(app)
    mongo = PyMongo(app)
    filter_keys = ['all', 'type', 'setname', 'buildname', 'jailname', 'server']

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

    def _get_builds(selector, projection=None):
        return {'filter': selector,
                'builds': list(mongo.db.builds.find(selector, projection).sort([
                    ('started', pymongo.DESCENDING),
                    ('setname', pymongo.ASCENDING),
                    ('ptname', pymongo.ASCENDING),
                    ('jailname', pymongo.ASCENDING),
                    ('buildname', pymongo.ASCENDING),
                    ]))}

    # Mongo does not allow '.' in keys due to dot-notation.
    def fix_port_origins(ports):
        if 'pkgnames' not in ports:
            return
        for origin in list(ports['pkgnames'].keys()):
            if '%' in origin:
                fixed_origin = origin.replace('%', '.')
                ports['pkgnames'][fixed_origin] = ports['pkgnames'].pop(origin)
                for field in ['built', 'failed', 'skipped', 'ignored']:
                    if field in ports and origin in ports[field]:
                        ports[field][fixed_origin] = ports[field].pop(origin)

    def get_server_map():
        return {x["_id"]:x for x in list(mongo.db.servers.find({},
            {'masternames': 0}))}

    @app.route('/')
    def index():
        return builds()

    @app.route('/servers.js')
    def servers_js():
        return make_response("var servers = %s;" % (json.dumps(get_server_map())),
                200, {'Content-Type': 'text/javascript'})

    def _get_filter():
        query = {'latest': True}
        projection = {
                'jobs': False,
                'snap.now': False,
        }
        latest = True
        if request.args is not None:
            for key, value in request.args.items():
                if key in filter_keys:
                    query[key] = value
            filter = query.copy()
            if "setname" in query:
                if query['setname'] == "default":
                    query['setname'] = ''
            if "all" in query or "buildname" in query:
                if "all" in query:
                    del(query['all'])
                del(query['latest'])
                latest = False
            if "type" in query:
                build_types = query['type'].split(',')
                query['type'] = {'$in': build_types}
        return (query, projection, filter)

    def _builds():
        query, projection, filter = _get_filter()
        build_results = _get_builds(query, projection)

        filter_qs_filter = filter.copy()
        if 'type' in filter_qs_filter:
            del filter_qs_filter['type']
        filter_qs = urlencode(filter_qs_filter)

        return {'builds': build_results['builds'],
                'filter': build_results['filter'],
                'filter_qs': filter_qs}

    @app.route('/api/1/builds')
    def api_builds():
        results = _builds()
        del results['filter_qs']
        return jsonify(results)

    @app.route('/builds')
    def builds():
        results = _builds()
        results['servers'] = get_server_map()
        return render_template('builds.html', **results)

    def _build(buildid):
        build = mongo.db.builds.find_one_or_404({'_id': buildid})
        ports = mongo.db.ports.find_one({'_id': buildid})
        if ports is not None:
            fix_port_origins(ports)
        return {'build': build, 'ports': ports}

    @app.route('/api/1/builds/<buildid>')
    def api_build(buildid):
        results = _build(buildid)
        return jsonify(results)

    @app.route('/builds/<buildid>')
    def build(buildid):
        results = _build(buildid)
        results['servers'] = get_server_map()
        return render_template('build.html', **results)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
