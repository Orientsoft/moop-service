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

# envs
LOG_LEVEL = int(os.getenv('LOG_LEVEL', ''))
TENANT_SERVICE_URL = os.environ.get('TENANT_SERVICE_URL', '/').strip()
NFS_SERVER = os.environ.get('NFS_SERVER', '/').strip()
NFS_PREFIX = os.environ.get('NFS_PREFIX', '/').strip()

# consts
SERVICE_PREFIX = '/volumes'
API_VERSION = 'service/v1'

# logger
LOG_NAME = 'Volume-Service'
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

        # read templates from tenant service
        tenant_resp = requests.get('{}/{}'.format(TENANT_SERVICE_URL, req_body.tenant))
        if tenant_resp.status_code != 200:
            logger.error('Request Error: {}\nStack: {}\n'.format(tenant_resp.json(), trackback.format_exc()))
            return Response(
                json.dumps({'error': 'tenant service returned failure'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

        templates = tenant_resp.json().resources.templates

        # TODO : get request resource type
        url_array = request.url.strip('/').split('/')
        resource_type = url_array[-1]
        print(resource_type)

        # create body
        if resource_type == 'pvs':
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

def get_params(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        params = request.args()

        if 'tenant' not in params.keys():
            return Response(
                json.dumps({'error': 'no tenant parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        if 'username' not in params.keys():
            return Response(
                json.dumps({'error': 'no username parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

        # read name from tenant service
        tenant_resp = requests.get('{}/{}'.format(TENANT_SERVICE_URL, params.tenant))
        if tenant_resp.status_code != 200:
            logger.error('Request Error: {}\nStack: {}\n'.format(tenant_resp.json(), trackback.format_exc()))
            return Response(
                json.dumps({'error': 'tenant service returned failure'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

        return f(
            tenant,
            username,
            *args,
            tenant_name=tenant_resp.json()['name'],
            **kwargs
        )

    return decorated

# POST /pvs
@app.route('/{}{}/pvs'.format(API_VERSION, SERVICE_PREFIX), methods['POST'])
@create_body
def create_pv(body):
    try:
        include_uninitialized = True
        pretty = 'true'

        pv = api_instance.create_persistent_volume(
            body,
            include_uninitialized=include_uninitialized,
            pretty=pretty
        )

        return Resopnse(
            json.dumps(pv, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, trackback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
        )

# GET /pvs
@app.route('/{}{}/pvs'.format(API_VERSION, SERVICE_PREFIX), methods=['GET'])
@get_params
def read_pv(tenant, username):
    try:
        pv_name = 'pv-{}-{}'.format(tenant, username)
        pretty = 'true'
        exact = True

        pv = api_instance.read_persistent_volume(
            pv_name,
            pretty=pretty,
            exact=exact
        )

        pv_status = api_instance.read_persistent_volume_status(
            pv_name,
            pretty=pretty
        )

        pv['status'] = pv_status

        return Resopnse(
            json.dumps(pv, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, trackback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
        )

# DELETE /pvs
@app.route('/{}{}/pvs'.format(API_VERSION, SERVICE_PREFIX), methods=['DELETE'])
@get_params
def read_pv(tenant, username):
    try:
        pv_name = 'pv-{}-{}'.format(tenant, username)

        pv = api_instance.delete_persistent_volume(pv_name)

        return Resopnse()
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, trackback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
        )

# POST /pvcs
@app.route('/{}{}/pvcs'.format(API_VERSION, SERVICE_PREFIX), methods=['POST'])
@create_body
def create_pvc(body):
    try:
        include_uninitialized = True
        pretty = 'true'

        pvc = api_instance.create_namespaced_persistent_volume_claim(
            body.namespace,
            body,
            include_uninitialized=include_uninitialized,
            pretty=pretty
        )

        return Resopnse(
            json.dumps(pvc, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, trackback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
        )

# GET /pvcs
@app.route('/{}{}/pvcs'.format(API_VERSION, SERVICE_PREFIX), methods=['GET'])
@get_params
def read_pv(tenant, username, tenant_name=''):
    try:
        pvc_name = 'pvc-{}-{}'.format(tenant, username)
        namespace = tenant_name
        pretty = 'true'
        exact = True

        pvc = api_instance.read_namespaced_persistent_volume_claim(
            pvc_name,
            pretty=pretty,
            exact=exact
        )

        pvc_status = api_instance.read_namespaced_persistent_volume_claim_status(
            pvc_name,
            namespace,
            pretty=pretty
        )

        pvc['status'] = pvc_status

        return Resopnse(
            json.dumps(pvc, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, trackback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
        )

# DELETE /pvs
@app.route('/{}{}/pvs'.format(API_VERSION, SERVICE_PREFIX), methods=['DELETE'])
@get_params
def read_pv(tenant, username, tenant_name=''):
    try:
        pvc_name = 'pvc-{}-{}'.format(tenant, username)
        namespace = tenant_name

        pvc = api_instance.delete_namespaced_persistent_volume_claim(pvc_name)

        return Resopnse()
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, trackback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
        )
