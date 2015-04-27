#!/usr/bin/python
# The MIT License (MIT)
#
# Copyright (c) 2015 Eran Sandler
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import subprocess
import os.path
import time
from os.path import expanduser
try:
    import simplejson as json
except ImportError:
    import json

_gcloud_exists = None

INSTANCES_CACHE = None
INSTANCES_NAME_INDEX = {}
INSTANCES_IP_INDEX = {}

def _check_gcloud():
    gcloud_version = None
    try:
        gcloud_version = subprocess.check_output("gcloud version", shell=True)
    except subprocess.CalledProcessError:
        raise Exception("Failed to run 'gcloud version'. That means you don't have gcloud installed or it's not part of the path.\nTo install gcutil see https://cloud.google.com/sdk/\nPrevious versions of fabric_gce_tools used gcutil which is about to be deprecated.")

    _gcloud_exists = (gcloud_version != None)

def _build_instances_index():
    global INSTANCES_NAME_INDEX
    global INSTANCES_IP_INDEX
    INSTANCES_NAME_INDEX = {}
    INSTANCES_IP_INDEX= {}

    for instance in INSTANCES_CACHE:
        if not instance["name"] in INSTANCES_NAME_INDEX:
            INSTANCES_NAME_INDEX[instance["name"]] = instance

        ip = instance["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
        if not ip in INSTANCES_IP_INDEX:
            INSTANCES_IP_INDEX[ip] = instance

def _get_data(use_cache, cache_expiration=86400, force_cache_refresh=False):
    global INSTANCES_CACHE

    loaded_cache = False
    execute_command = True
    data = None

    cache_path = os.path.join(expanduser("~"), ".gcetools")
    cache_file_path = os.path.join(cache_path, "instances")

    if use_cache and not force_cache_refresh:
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)

        if os.path.exists(cache_file_path):
            created_timestamp = os.path.getctime(cache_file_path)
            if created_timestamp + cache_expiration > time.time():
                f = open(cache_file_path, "r")
                try:
                    raw_data = f.read()
                    data = json.loads(raw_data)
                    execute_command = False
                    loaded_cache = True
                finally:
                    f.close()

    if execute_command:
        global _gcloud_exists

        if _gcloud_exists is None:
            _check_gcloud()
        else:
            if not _gcloud_exists:
                raise Exception("Can't find 'gcloud'. That means you don't have gcutil installed or it's not part of the path.\nTo install gcutil see https://cloud.google.com/sdk/")

        raw_data = subprocess.check_output("gcloud compute instances list --format=json", shell=True)
        data = json.loads(raw_data)

        if (use_cache and not loaded_cache) or force_cache_refresh:
            f = open(cache_file_path, "w")
            try:
                f.write(raw_data)
            finally:
                f.close()

    INSTANCES_CACHE = data
    _build_instances_index()
    return data

def _get_roles(data):
    roles = {}
    for i in data:
        if "tags" in i and i["tags"] and "items" in i["tags"]:
            for t in i["tags"]["items"]:
                role = t
                if not role in roles:
                    roles[role] = []

                address = i["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
                if not address in roles[role]:
                    roles[role].append(address)

    return roles

def get_instance_by_name(name):
    if name in INSTANCES_NAME_INDEX:
        return INSTANCES_NAME_INDEX[name]

    return None

def get_instance_zone_by_name(name):
    instance = get_instance_by_name(name)
    if instance:
        return instance["zone"]

    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("instance_name", help="The name of the instance you wish to connect to")
    parser.add_argument("-r", "--refresh_instances_cache", action="store_true", help="Force refreshing the instances list cache")
    args = parser.parse_args()

    instance_name = args.instance_name
    refresh_cache = args.refresh_instances_cache

    _get_data(True, force_cache_refresh=refresh_cache)

    instance_zone = get_instance_zone_by_name(instance_name)
    cmd_args = ["gcloud", "compute", "ssh", instance_name, "--zone={0}".format(instance_zone)]
    subprocess.call(cmd_args)

if __name__ == "__main__":
    main()
