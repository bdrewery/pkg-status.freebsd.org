import datetime
import json
from flask import Flask, jsonify, render_template, request
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

    def _get_builds(selector):
        return {'filter': selector,
                'builds': list(mongo.db.builds.find(selector).sort([
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
        return builds()

    def _ports(filter, origin):
        ports_filter = {'$or': []}
        for key_type in ['built', 'failed', 'skipped', 'ignored']:
            ports_filter['$or'].append({"%s.%s" % (key_type, origin): {
                '$exists': True}})
        buildids = list(mongo.db.ports.find(ports_filter, {'_id': ''}))
        print(ports_filter)
        print(buildids)
        return _builds(filter)

    def _builds(filter):
        query = {'latest': True}
        latest = True
        if filter is not None:
            for key, value in filter.iteritems():
                query[key] = value
            if "setname" in query:
                if query['setname'] == "default":
                    query['setname'] = ''
            if "all" in query:
                del(query['all'])
                del(query['latest'])
                latest = False
            if "type" in query:
                build_types = query['type'].split(',')
                query['type'] = {'$in': build_types}
        build_results = _get_builds(query)
        return {'builds': build_results['builds'],
                'filter': build_results['filter']}

    @app.route('/api/1/builds')
    def api_builds():
        results = _builds(request.args.get('filter', {}))
        return jsonify(results)

    @app.route('/builds')
    def builds():
        results = _builds(request.args)
        results['servers'] = get_server_map()
        return render_template('builds.html', **results)

    @app.route('/ports/<path:origin>')
    def ports(origin):
        results = _ports(request.args, origin)
        results['servers'] = get_server_map()
        return jsonify(results)
#        return render_template('builds.html', **results)

    def _build(buildid):
        build = mongo.db.builds.find_one_or_404({'_id': buildid})
        ports = mongo.db.ports.find_one({'_id': buildid})
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
