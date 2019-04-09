from __future__ import print_function
from functools import wraps
import traceback
import time
import json
import os
import logging
import logging.handlers
import sys
import datetime

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

# helper
def datetime_convertor(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()

# load kube config from .kube
config.load_kube_config()

# create an instance of the API class
api_instance = kubernetes.client.CoreV1Api()

app = Flask(__name__)

def create_body(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # parameters
        req_body = request.get_json()

        # get request resource type
        url_array = request.url.strip('/').split('/')
        resource_type = url_array[-1]

        if 'tenant' not in req_body.keys():
            return Response(
                json.dumps({'error': 'no tenant parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        if 'username' not in req_body.keys():
            return Response(
                json.dumps({'error': 'no username parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        if 'path' not in req_body.keys() and resource_type == 'pvs':
            return Response(
                json.dumps({'error': 'no path parameter specified for pv'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        tag = req_body['tag'] if 'tag' in req_body.keys() else 'default'
        match = req_body['match'] if 'match' in req_body.keys() else False

        # read templates from tenant service
        tenant_resp = requests.get('{}/{}'.format(TENANT_SERVICE_URL, req_body['tenant']))
        if tenant_resp.status_code != 200:
            logger.error('Request Error: {}\nStack: {}\n'.format(tenant_resp.json(), traceback.format_exc()))
            return Response(
                json.dumps({'error': 'tenant service returned failure'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

        tenant = tenant_resp.json()
        namespace = tenant['namespace']
        templates = tenant['resources']['templates']

        # create body
        if resource_type == 'pvs':
            body = templates['pv']

            body['metadata']['name'] = body['metadata']['name'].format(req_body['tenant'], req_body['username'], tag)
            body['metadata']['namespace'] = namespace
            body['metadata']['labels']['pv'] = body['metadata']['labels']['pv'].format(req_body['tenant'], req_body['username'], tag)
            body['spec']['nfs']['server'] = body['spec']['nfs']['server'].format(NFS_SERVER)
            body['spec']['nfs']['path'] = body['spec']['nfs']['path'].format(NFS_PREFIX, req_body['path'])
        else:
            if match:
                body = templates['match_pvc']

                body['metadata']['name'] = body['metadata']['name'].format(req_body['tenant'], req_body['username'], tag)
                body['metadata']['namespace'] = namespace
                body['spec']['selector']['matchLabels']['pv'] = body['spec']['selector']['matchLabels']['pv'].format(req_body['tenant'], req_body['username'], tag)
            else:
                body = templates['pvc']

                body['metadata']['name'] = body['metadata']['name'].format(req_body['tenant'], req_body['username'], tag)
                body['metadata']['namespace'] = namespace

        return f(
            body,
            *args,
            **kwargs
        )

    return decorated

def get_params(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        params = request.args.to_dict()

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
        tag = params['tag'] if 'tag' in params.keys() else 'default'

        # read name from tenant service
        tenant_resp = requests.get('{}/{}'.format(TENANT_SERVICE_URL, params['tenant']))
        if tenant_resp.status_code != 200:
            logger.error('Request Error: {}\nStack: {}\n'.format(tenant_resp, traceback.format_exc()))
            return Response(
                json.dumps({'error': 'tenant service returned failure'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

        return f(
            params['tenant'],
            params['username'],
            tag,
            *args,
            namespace=tenant_resp.json()['namespace'],
            **kwargs
        )

    return decorated

# POST /pvs
@app.route('/{}{}/pvs'.format(API_VERSION, SERVICE_PREFIX), methods=['POST'])
@create_body
def create_pv(body):
    try:
        include_uninitialized = True
        pretty = 'true'

        pv = api_instance.create_persistent_volume(
            body,
            include_uninitialized=include_uninitialized,
            pretty=pretty
        ).to_dict()

        return Response(
            json.dumps(pv, default=datetime_convertor, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
            status=400
        )
    except Exception as e:
        # this might be a bug
        logger.critical('Program Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps(
                {'error': 'Volume service failed.'},
                indent=1,
                sort_keys=True
            ),
            status=500,
            mimetype='application/json'
        )

# GET /pvs
@app.route('/{}{}/pvs'.format(API_VERSION, SERVICE_PREFIX), methods=['GET'])
@get_params
def read_pv(tenant, username, tag, namespace=''):
    try:
        pv_name = 'pv-{}-{}-{}'.format(tenant, username, tag)
        pretty = 'true'
        exact = True

        pv_status = api_instance.read_persistent_volume_status(
            pv_name,
            pretty=pretty
        ).to_dict()

        return Response(
            json.dumps(pv_status, default=datetime_convertor, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
            status=400
        )
    except Exception as e:
        # this might be a bug
        logger.critical('Program Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps(
                {'error': 'Volume service failed.'},
                indent=1,
                sort_keys=True
            ),
            status=500,
            mimetype='application/json'
        )

# DELETE /pvs
@app.route('/{}{}/pvs'.format(API_VERSION, SERVICE_PREFIX), methods=['DELETE'])
@get_params
def remove_pv(tenant, username, tag, namespace=''):
    try:
        pv_name = 'pv-{}-{}-{}'.format(tenant, username, tag)

        pv = api_instance.delete_persistent_volume(pv_name)

        return Response()
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
            status=400
        )
    except Exception as e:
        # this might be a bug
        logger.critical('Program Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps(
                {'error': 'Volume service failed.'},
                indent=1,
                sort_keys=True
            ),
            status=500,
            mimetype='application/json'
        )

# POST /pvcs
@app.route('/{}{}/pvcs'.format(API_VERSION, SERVICE_PREFIX), methods=['POST'])
@create_body
def create_pvc(body):
    try:
        include_uninitialized = True
        pretty = 'true'

        print(body)
        pvc = api_instance.create_namespaced_persistent_volume_claim(
            body['metadata']['namespace'],
            body,
            include_uninitialized=include_uninitialized,
            pretty=pretty
        ).to_dict()

        return Response(
            json.dumps(pvc, default=datetime_convertor, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
            status=400
        )
    except Exception as e:
        # this might be a bug
        logger.critical('Program Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps(
                {'error': 'Volume service failed.'},
                indent=1,
                sort_keys=True
            ),
            status=500,
            mimetype='application/json'
        )

# GET /pvcs
@app.route('/{}{}/pvcs'.format(API_VERSION, SERVICE_PREFIX), methods=['GET'])
@get_params
def read_pvc(tenant, username, tag, namespace=''):
    try:
        pvc_name = 'pvc-{}-{}-{}'.format(tenant, username, tag)
        pretty = 'true'
        exact = True

        pvc_status = api_instance.read_namespaced_persistent_volume_claim_status(
            pvc_name,
            namespace,
            pretty=pretty
        ).to_dict()

        return Response(
            json.dumps(pvc_status, default=datetime_convertor, indent=1, sort_keys=True),
            mimetype='application/json'
        )
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
            status=400
        )
    except Exception as e:
        # this might be a bug
        logger.critical('Program Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps(
                {'error': 'Volume service failed.'},
                indent=1,
                sort_keys=True
            ),
            status=500,
            mimetype='application/json'
        )

# DELETE /pvcs
@app.route('/{}{}/pvcs'.format(API_VERSION, SERVICE_PREFIX), methods=['DELETE'])
@get_params
def remove_pvc(tenant, username, tag, namespace=''):
    try:
        pvc_name = 'pvc-{}-{}-{}'.format(tenant, username, tag)

        pvc = api_instance.delete_namespaced_persistent_volume_claim(
            pvc_name,
            namespace
        )

        return Response()
    except ApiException as e:
        logger.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps({'error': 'Kubernetes API request failed'}, indent=1, sort_keys=True),
            mimetype='application/json',
            status=400
        )
    except Exception as e:
        # this might be a bug
        logger.critical('Program Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return Response(
            json.dumps(
                {'error': 'Volume service failed.'},
                indent=1,
                sort_keys=True
            ),
            status=500,
            mimetype='application/json'
        )
