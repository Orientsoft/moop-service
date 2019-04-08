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
import uuid

from kubernetes import config
import kubernetes.client
from kubernetes.client.rest import ApiException

import requests
from flask import Flask, redirect, request, Response

# envs
LOG_LEVEL = int(os.getenv('LOG_LEVEL', ''))
TENANT_SERVICE_URL = os.environ.get('TENANT_SERVICE_URL', '/').strip()

# consts
SERVICE_PREFIX = '/pods'
API_VERSION = 'service/v1'

# logger
LOG_NAME = 'Pod-Service'
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

# helper
def datetime_convertor(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()

app = Flask(__name__)

def create_body(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # parameters
        req_body = request.get_json()

        if 'tenant' not in req_body.keys():
            return Response(
                json.dumps({'error': 'no tenant parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        if 'cmd' not in req_body.keys():
            return Response(
                json.dumps({'error': 'no cmd parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        vols = req_body['vols'] if 'vols' in req_body.keys() else []

        # read templates from tenant service
        tenant_resp = requests.get('{}/{}'.format(TENANT_SERVICE_URL, req_body['tenant']))
        if tenant_resp.status_code != 200:
            logger.error('Request Error: {}\nStack: {}\n'.format(tenant_resp.json(), traceback.format_exc()))
            return Response(
                json.dumps({'error': 'tenant service returned failure'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

        tenant = tenant_resp.json()
        templates = tenant['resources']['templates']
        namespace = tenant['namespace']

        # create body
        body = templates['pod']
        body['metadata']['name'] = body['metadata']['name'].format(
            tenant['id'],
            uuid.uuid4()
        )
        body['spec']['containers'][0]['args'][2] = req_body['cmd']

        # create volumeMounts and volumes from vols
        vol_names = [str(uuid.uuid4()) for vol in vols]
        volumes = []
        volumeMounts = []
        for i, vol in enumerate(vols):
            volumes.append(
                {
                    'name': vol_names[i],
                    'persistentVolumeClaim':
                    {
                        'claimName': vol['pvc']
                    }
                }
            )

            volumeMounts.append(
                {
                    'name': vol_names[i],
                    'mountPath': vol['mount']
                }
            )

        body['spec']['containers'][0]['volumeMounts'] = volumeMounts
        body['spec']['volumes'] = volumes

        return f(
            body,
            req_body,
            *args,
            namespace=namespace,
            **kwargs
        )

    return decorated

def get_params(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # parameters
        req_body = request.args.to_dict()

        if 'tenant' not in req_body.keys():
            return Response(
                json.dumps({'error': 'no tenant parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )
        if 'name' not in req_body.keys():
            return Response(
                json.dumps({'error': 'no name parameter specified'}, indent=1, sort_keys=True),
                mimetype='application/json',
            )

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

        return f(
            req_body,
            *args,
            namespace=namespace,
            **kwargs
        )

    return decorated

# POST /pods
@app.route('/{}{}'.format(API_VERSION, SERVICE_PREFIX), methods=['POST'])
@create_body
def create_pod(body, req_body, namespace=''):
    try:
        pod = api_instance.create_namespaced_pod(
            body=body,
            namespace=namespace
        ).to_dict()

        return Response(
            json.dumps(
                pod,
                default=datetime_convertor,
                indent=1,
                sort_keys=True
            ),
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

# GET /pods
@app.route('/{}{}'.format(API_VERSION, SERVICE_PREFIX), methods=['GET'])
@get_params
def read_pod(req_body, namespace=''):
    try:
        pod = api_instance.read_namespaced_pod(
            name=req_body['name'],
            namespace=namespace
        ).to_dict()

        return Response(
            json.dumps(
                pod,
                default=datetime_convertor,
                indent=1,
                sort_keys=True
            ),
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

# DELETE /pods
@app.route('/{}{}'.format(API_VERSION, SERVICE_PREFIX), methods=['DELETE'])
@get_params
def remove_pod(req_body, namespace=''):
    try:
        pod = api_instance.delete_namespaced_pod(
            name=req_body['name'],
            namespace=namespace
        ).to_dict()

        return Response(
            json.dumps(
                pod,
                default=datetime_convertor,
                indent=1,
                sort_keys=True
            ),
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
