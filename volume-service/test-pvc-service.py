from __future__ import print_function
from functools import wraps
import traceback
import time
import json
import os
import logging
import logging.handlers
import sys

from kubernetes import config
import kubernetes.client
from kubernetes.client.rest import ApiException

import requests
from flask import Flask, redirect, request, Response

TENANT_SERVICE_URL = os.environ.get('TENANT_SERVICE_URL', '/').strip()
NFS_SERVER = os.environ.get('NFS_SERVER', '/').strip()
NFS_PREFIX = os.environ.get('NFS_PREFIX', '/').strip()

# logger
LOG_NAME = 'Launcher-Service'
LOG_FORMAT = '%(asctime)s - %(filename)s:%(lineno)s - %(name)s:%(funcName)s - [%(levelname)s] %(message)s'

def setup_logger(level):
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    logger = logging.getLogger(LOG_NAME)
    logger.addHandler(handler)
    logger.setLevel(level)

    return logger

logger = setup_logger(int(LOG_LEVEL))

# load kube config from .kube
config.load_kube_config()

# create an instance of the API class
api_instance = kubernetes.client.CoreV1Api()

app = Flask(__name__)

def create_body(f):
    @wraps(f)
    def decorated(type, *args, **kwargs):
        # parameters
        req_body = request.get_json()

        if 'tenant' not in body.keys():
            return Response(
                json.dumps({'error': 'no tenant parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        if 'username' not in body.keys():
            return Response(
                json.dumps({'error': 'no username parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

        # TODO : read template from tenant service & convert to dict
        templates = json.loads(resources)

        if type == 'pv':
            body = templates['pv']

            body.metadata.name.format(req_body.tenant, req_body.username)
            body.metadata.namespace.format(tenant.name)
            body.metadata.labels.pv.format(req_body.tenant, req_body.username)
            body.spec.nfs.server.format(NFS_SERVER)
            body.spec.nfs.path.format(NFS_PREFIX, req_body.tenant, req_body.username)
        else:
            body = templates['pvc']

            body.metadata.name.format(req_body.tenant, req_body.username)
            body.metadata.namespace.format(tenant.name)
            body.spec.selector.matchLabels.pv.format(req_body.tenant, req_body.username)

        return f(
            body,
            *args,
            **kwargs
        )

    return decorated

body = {
    "apiVersion": "v1",
    "kind": "PersistentVolumeClaim",
    "metadata": {
        "name": "pvc-{}-{}".format('test', 'script'),
        "namespace": "{}".format('jhub-46'),
    },
    "spec": {
        "accessModes": ["ReadWriteMany"],
        "resources": {
            "requests": {
                "storage": "100Mi"
            }
        },
        "selector": {
            "matchLabels": {
                "pv": "pv-{}-{}".format('test', 'script') # pv name template: "pv-{tenant_id}-{username}"
            }
        }
    }
}

namespace = 'jhub-46'

include_uninitialized = True # bool | If true, partially initialized resources are included in the response. (optional)
pretty = 'true' # str | If 'true', then the output is pretty printed. (optional)
dry_run = 'All' # str | When present, indicates that modifications should not be persisted. An invalid or unrecognized dryRun directive will result in an error response and no further processing of the request. Valid values are: - All: all dry run stages will be processed (optional)

try: 
    api_response = api_instance.create_namespaced_persistent_volume_claim(namespace, body, include_uninitialized=include_uninitialized, pretty=pretty, dry_run=dry_run)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling CoreV1Api->create_persistent_volume: %s\n" % e)
