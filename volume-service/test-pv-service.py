from __future__ import print_function
import time
from kubernetes import config
import kubernetes.client
from kubernetes.client.rest import ApiException
from pprint import pprint

config.load_kube_config()

# Configure API key authorization: BearerToken
#configuration = kubernetes.client.Configuration()
#configuration.api_key['authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['authorization'] = 'Bearer'

# create an instance of the API class
#api_instance = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient(configuration))
api_instance = kubernetes.client.CoreV1Api()
# body = kubernetes.client.V1PersistentVolume() # V1PersistentVolume | 

body = {
    "apiVersion": "v1",
    "kind": "PersistentVolume",
    "metadata": {
        "name": "pv-{}-{}".format('test', 'script'),
        "namespace": "{}".format('jhub-46'),
        "labels": {
            "pv": "pv-{}-{}".format('test', 'script'),
        }
    },
    "spec": {
        "accessModes": ["ReadWriteMany"],
        "capacity": {
            "storage": "100Mi"
        },
        "nfs": {
            "server": "[nfs-server]",
            "path": "/[nfs-prefix]/{}-{}".format('test', 'script')
        }
    }
}

include_uninitialized = True # bool | If true, partially initialized resources are included in the response. (optional)
pretty = 'true' # str | If 'true', then the output is pretty printed. (optional)
dry_run = 'All' # str | When present, indicates that modifications should not be persisted. An invalid or unrecognized dryRun directive will result in an error response and no further processing of the request. Valid values are: - All: all dry run stages will be processed (optional)

try: 
    api_response = api_instance.create_persistent_volume(body, include_uninitialized=include_uninitialized, pretty=pretty, dry_run=dry_run)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling CoreV1Api->create_persistent_volume: %s\n" % e)
