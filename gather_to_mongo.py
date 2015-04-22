#! /usr/bin/env python

import requests
import sys
import pymongo

def fetch_data(server, path):
    url = "http://%s%s" % (server, path)
    print("Fetching %s" % url)
    try:
        response = requests.get(url, timeout=0.5)
    except requests.exceptions.ConnectionError:
        print("Connection error to %s" % url)
        return None
    except requests.exceptions.ReadTimeout:
        print("Timeout to %s" % url)
        return None
    if response.status_code == 200:
        json = response.json()
        return json
    return None

def gather_masternames(server):
    json = fetch_data(server, "/data/.data.json")
    if not json or "masternames" not in json:
        return None
    return [(mastername, build["latest"]["buildname"],
        build["setname"], build["ptname"], build["jailname"])
            for mastername, build in json["masternames"].iteritems()]

def gather_builds(server, mastername):
    json = fetch_data(server, "/data/%s/.data.json" % mastername)
    if not json or "builds" not in json:
        return None
    return json["builds"]

def gather_build_info(server, mastername, build):
    json = fetch_data(server, "/data/%s/%s/.data.json" % (mastername, build))
    if not json or "buildname" not in json:
        return None
    return json

def build_id(setname, ptname, jailname, build, server):
    return "%s:%s:%s:%s:%s" % (setname, ptname, jailname, build,
            server.split('.')[0])

def build_id_to_mastername(buildid):
    tmp = buildid.split(':')
    setname = ""
    if tmp[1] != "default":
        setname = "-" + tmp[1]
    mastername = tmp[3] + "-" + tmp[2] + setname
    return mastername

def build_id_to_server(buildid):
    return buildid.split(':')[0]

def build_id_to_buildname(buildid):
    return buildid.split(':')[4]

conn = pymongo.Connection()
db = conn.pkgstatus

with open("servers.txt", "r") as f:
    for line in f:
        if line[0] == "#":
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
            db.servers.insert(server_info)
        for mastername, latest_build, setname, ptname, jailname in masternames:
            # If the latest build has not changed then skip fetching more.
            if mastername in server_info["masternames"] and latest_build == \
                    server_info["masternames"][mastername]["latest"]:
                continue
            elif mastername not in server_info["masternames"]:
                server_info["masternames"][mastername] = {}
            server_info["masternames"][mastername]["latest"] = latest_build
            builds = gather_builds(server, mastername)
            if builds is None:
                continue
            print("Importing mastername %s/%s" % (server, mastername))

            # Prepare the dst dict.
            if len(setname) == 0:
                setname = "default" # Don't do this

            # XXX: Archive deleted builds
            for buildname, build_info_sparse in builds.iteritems():
                if buildname == "latest":
                    buildname = build_info_sparse
                    buildid = build_id(setname, ptname, jailname, buildname, server)
                    db.builds.update({"mastername": mastername,
                        "server": server_short, "latest": True},
                        {"$unset": {"latest": ""}})
                    db.builds.update({"_id": buildid},
                            {"$set": {"latest": True}})
                    continue
                buildid = build_id(setname, ptname, jailname, buildname, server)
                # Ignore some legacy builds
                if "status" not in build_info_sparse:
                    continue
                build = db.builds.find_one({"_id": buildid})
                # Don't update existing "stopped:" builds.
                if build is not None and build["status"][0:7] == "stopped":
                        continue

                # Fetch the full build information
                build_info = gather_build_info(server, mastername, buildname)

                # XXX: This is not importable due to pkgname keys having '.'
                if "skipped" in build_info:
                    del(build_info["skipped"])
                for key, value in build_info["stats"].iteritems():
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

                # Trim idle jobs to save db space
                if "jobs" in build_info:
                    build_info["jobs"] = [job for job in
                            build_info["jobs"] if job["status"] != "idle:"]

                if "ports" in build_info:
                    build_info["ports"]["_id"] = buildid
                    db.ports.update({"_id": buildid}, build_info["ports"],
                            upsert=True)
                    del(build_info["ports"])

                build_info["_id"] = buildid
                build_info["server"] = server_short
                build_info["type"] = server_type
                if build is not None:
                    print("Updating %s / %s: %s" % (mastername, buildname,
                        buildid))
                    db.builds.update({"_id": buildid}, build_info)
                else:
                    print("Insert %s / %s: %s" % (mastername, buildname,
                        buildid))
                    db.builds.insert(build_info)
        db.servers.update({"_id": server_short}, server_info)
    qat_sets = ["qat", "baseline", "build-as-user"]
    db.builds.update({"type": "exp", "setname": qat_sets},
            {"$set": {"type": "qat"}}, multi=True)
