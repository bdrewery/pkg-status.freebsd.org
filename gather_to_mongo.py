#!/usr/bin/env python3

import requests
import sys
import pymongo
import re
import os

def fetch_data(server, path):
    proxy_server = os.getenv("PKGSTATUS_GATHER_PROXY_SERVER")

    if proxy_server:
        url = f"{proxy_server}/{server.split('.')[0]}{path}"
    else:
        url = f"http://{server}{path}"
    print(f"Fetching {url}")
    try:
        response = requests.get(url, timeout=0.5)
    except requests.exceptions.ConnectionError:
        print(f"Connection error to {url}")
        return None
    except requests.exceptions.ReadTimeout:
        print(f"Timeout to {url}")
        return None
    if response.status_code == 200:
        try:
            return response.json()
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return None
    return None

def gather_masternames(server):
    json = fetch_data(server, "/data/.data.json")
    if not json or "masternames" not in json:
        return None
    return [(mastername, build["latest"],
        build["setname"], build["ptname"], build["jailname"])
            for mastername, build in json["masternames"].items()]

def gather_builds(server, mastername):
    json = fetch_data(server, f"/data/{mastername}/.data.json")
    if not json or "builds" not in json:
        return None
    return json["builds"]

def gather_build_info(server, mastername, build):
    json = fetch_data(server, f"/data/{mastername}/{build}/.data.json")
    if not json or "buildname" not in json:
        return None
    return json

def build_id(setname, ptname, jailname, build, server):
    return f"{setname}:{ptname}:{jailname}:{build}:{server.split('.')[0]}"

def build_id_to_mastername(buildid):
    tmp = buildid.split(':')
    setname = ""
    if tmp[1] != "default":
        setname = "-" + tmp[1]
    mastername = f"{tmp[3]}-{tmp[2]}{setname}"
    return mastername

def build_id_to_server(buildid):
    return buildid.split(':')[0]

def build_id_to_buildname(buildid):
    return buildid.split(':')[4]

def calc_started(build_info):
    if "started" in build_info:
        build_info['started'] = int(build_info['started'])
    elif "snap" in build_info and "now" in build_info['snap'] \
            and "elapsed" in build_info['snap']:
        build_info['started'] = build_info['snap']['now'] - \
                build_info['snap']['elapsed']
    else:
        build_info['started'] = 0

def fix_port_origins(ports):
    pkgnames = {}
    # Gather all of the pkgnames and then remove them from each list
    # mongo doesn't allow '.' in keys so key by something else
    for key in ['built', 'failed', 'skipped', 'ignored']:
        if key in ports:
            new_obj = {}
            for obj in ports[key]:
                origin = obj['origin']
                origin_key = origin.replace('.', '%')
                pkgname = obj['pkgname']
                pkgnames[origin_key] = pkgname
                del obj['pkgname']
                del obj['origin']
                new_obj[origin_key] = obj
            ports[key] = new_obj
    ports['pkgnames'] = pkgnames

def process_new_failures(build, current=False):
    # Find the previous matching build or skip if there is none. Only consider
    # passing builds.
    if build['type'] in ["package", "qat"]:
        # Just compare package/qat runs to themselves.
        previous_build = list(db.builds.find({
            'mastername': build['mastername'], 'type': build['type'],
            'status': 'stopped:done:',
            'started': {'$lt': build['started']}}).sort(
                    [('started', pymongo.DESCENDING)]).limit(1))
    else:
        # Compare exp runs to a previous baseline
        # XXX
        return False

    if len(previous_build) == 0:
        return False
    previous_build = previous_build[0]
    print(f"Processing new failures for {build['_id']}. Previous build {previous_build['_id']}")

    # Fetch the full port list for both builds to determine changes
    result_keys = ['built', 'failed', 'skipped', 'ignored']
    query_filter = {x: '' for x in result_keys}
    query_filter['pkgnames'] = ''
    if current:
        previous_ports = db.ports.find_one({'_id': previous_build['_id']},
                query_filter)
        current_ports = build['ports']
    else:
        ports_list = db.ports.find({
            '_id': { '$in': [build['_id'], previous_build['_id']] } },
            query_filter)
        if ports_list[0]['_id'] == build['_id']:
            current_ports = ports_list[0]
            previous_ports = ports_list[1]
        else:
            previous_ports = ports_list[0]
            current_ports = ports_list[1]
        build['ports'] = current_ports
    # Determine differences and store back
    new_list = {}
    new_stats = {}
    for result_key in result_keys:
        if result_key not in current_ports:
            current_ports[result_key] = {}
        if result_key not in previous_ports:
            previous_ports[result_key] = {}
        new_list[result_key] = list(
                set([x.replace('%', '.') for x in current_ports[result_key]]) -
                set([x.replace('%', '.') for x in previous_ports[result_key]]))
        new_stats[result_key] = len(new_list[result_key])
    build['ports']['new'] = new_list
    build['new_stats'] = new_stats
    build['previous_id'] = previous_build['_id']
    return True


mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/pkgstatus')
client = pymongo.MongoClient(mongo_uri)
db = client['pkgstatus']
qat_sets = ["qat", "baseline", "build-as-user"]

# Repair start times
print("Reparing build start times.")
for build_info in db.builds.find({'started': {'$exists': False}}, {"_id": "",
    'snap.now': '', 'snap.elapsed': ''}):
    calc_started(build_info)
    print(f"Setting started to '{build_info['started']}' for {build_info['_id']}")
    db.builds.update_one({'_id': build_info['_id']}, {'$set': {'started': build_info['started']}})

# Import new data
print("Importing new data.")
with open("servers.txt", "r") as f:
    for line in f:
        if line.startswith("#"):
            continue
        line = line.strip().split(':')
        server_type = line[0]
        server = line[1]
        server_short = server.split('.')[0]
        masternames = gather_masternames(server)
        if masternames is None:
            continue
        server_info = db.servers.find_one({"_id": server_short})
        if server_info is None:
            server_info = {
                    "_id": server_short,
                    "type": server_type,
                    "host": server,
                    "masternames": {}
                    }
            db.servers.insert_one(server_info)
        for mastername, latest, setname, ptname, jailname in masternames:
            running_builds = True
            if mastername not in server_info["masternames"]:
                server_info["masternames"][mastername] = {
                        'latest': '',
                        'latest_status': ''
                        }
            if 'latest_status' not in server_info["masternames"][mastername]:
                server_info["masternames"][mastername]['latest_status'] = \
                        'unknown'
            if latest['status'].startswith('stopped') and \
                    latest['buildname'] == \
                    server_info["masternames"][mastername]["latest"] and \
                    latest['status'] == \
                    server_info["masternames"][mastername]["latest_status"]:
                continue
            server_info["masternames"][mastername]["latest"] = latest['buildname']
            server_info["masternames"][mastername]["latest_status"] = \
                    latest['status']
            builds = gather_builds(server, mastername)
            if builds is None:
                continue

            # Prepare the dst dict.
            if len(setname) == 0:
                setname = "default" # Don't do this

            # XXX: Archive deleted builds
            for buildname, build_info_sparse in builds.items():
                if buildname == "latest":
                    buildname = build_info_sparse
                    buildid = build_id(setname, ptname, jailname, buildname, server)
                    db.builds.update_many({"mastername": mastername,
                        "server": server_short, "latest": True},
                        {"$unset": {"latest": ""}})
                    db.builds.update_one({"_id": buildid},
                            {"$set": {"latest": True}})
                    continue
                buildid = build_id(setname, ptname, jailname, buildname, server)
                # Ignore some legacy builds
                if "status" not in build_info_sparse:
                    continue
                build = db.builds.find_one({"_id": buildid})
                # Don't update existing "stopped:" builds.
                if build is not None and build["status"].startswith("stopped"):
                        continue

                # Fetch the full build information
                build_info = gather_build_info(server, mastername, buildname)
                if build_info is None:
                    continue

                # XXX: This is not importable due to pkgname keys having '.'
                if "skipped" in build_info:
                    del build_info["skipped"]
                for key, value in build_info["stats"].items():
                    build_info["stats"][key] = int(value)
                try:
                    build_info["stats"]["remaining"] = \
                            build_info["stats"]["queued"] - (
                                    build_info["stats"]["built"] +
                                    build_info["stats"]["failed"] +
                                    build_info["stats"]["skipped"] +
                                    build_info["stats"]["ignored"])
                except:
                    # Probably a crashed build.
                    build_info["stats"]["remaining"] = 0

                if "snap" in build_info:
                    for snapkey in ["now", "elapsed"]:
                        if snapkey in build_info["snap"]:
                            build_info["snap"][snapkey] = \
                                    int(build_info["snap"][snapkey])
                # Convert and/or calculated started epoch time.
                calc_started(build_info)

                # Trim idle jobs to save db space
                if "jobs" in build_info:
                    build_info["jobs"] = [job for job in
                            build_info["jobs"] if job["status"] != "idle:"]

                build_info["_id"] = buildid
                build_info["server"] = server_short
                build_info["type"] = server_type
                if setname in qat_sets:
                    build_info["type"] = "qat"

                if "ports" in build_info:
                    build_info["ports"]["_id"] = buildid
                    fix_port_origins(build_info["ports"])
                    process_new_failures(build_info, current=True)
                    db.ports.update_one({"_id": buildid}, {"$set": build_info["ports"]},
                            upsert=True)
                    del build_info["ports"]

                if build is not None:
                    print(f"Updating {mastername} / {buildname}: {buildid}")
                    db.builds.update_one({"_id": buildid}, {'$set': build_info})
                else:
                    print(f"Insert {mastername} / {buildname}: {buildid}")
                    db.builds.insert_one(build_info)
        db.servers.update_one({"_id": server_short}, {"$set": server_info})

# Repair pkgnames
print("Fixing pkgnames.")
for portids in db.ports.find({'pkgnames': {'$exists': False}}, {"_id": ""}):
    # Fetch here rather than in the loop due to memory explosion
    ports = db.ports.find_one({'_id': portids['_id']},
        {x: '' for x in ['built', 'failed', 'skipped', 'ignored']})
    print(f"Fixing pkgnames for {portids['_id']}")
    fix_port_origins(ports)
    db.ports.update_one({'_id': portids['_id']}, {'$set': ports})

# Process new failures
print("Processing build failures and stats.")
for portids in db.ports.find({'new': {'$exists': False}},
        {"_id": ""}).sort([('_id', pymongo.ASCENDING)]):
    # This is not done above as it would load several GB of data.
    # Need to fetch current and previous build's data.

    # Get current build info
    build = db.builds.find_one({'_id': portids['_id'],
        'status': 'stopped:done:', 'started': {'$exists': True}},
        {'mastername': '', 'type': '', 'started': ''})
    # Ignore legacy data (no snap.now) and crashed builds.
    if build is None:
        db.ports.update_one({'_id': portids['_id']}, {'$set': {'new': []}})
        continue
    if not process_new_failures(build):
        continue
    db.ports.update_one({'_id': build['_id']},
            {'$set': {'new': build['ports']['new']}})
    db.builds.update_one({'_id': build['_id']},
            {'$set': {'new_stats': build['new_stats'],
                'previous_id': build['previous_id']}})

