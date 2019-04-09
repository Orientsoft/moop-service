# volume-service

K8s persistent volume management service, customized for MOOP API Server.  
## tenant resources

Save pv and pvc templates in tenant resources.templates field:  

pvTemplate:  

```js
{
    "apiVersion": "v1",
    "kind": "PersistentVolume",
    "metadata": {
        "name": "pv-{}-{}-{}", // pv name template: "pv-{tenant_id}-{username}-{tag}"
        "namespace": "{}", // pv namespace template: "{tenant_id}"
        "labels": {
            "pv": "pv-{}-{}-{}", // pv label template: "pv-{tenant_id}-{username}-{tag}"
        }
    },
    "spec": {
        "accessModes": ["ReadWriteMany"], // no use, but required by k8s
        "capacity": {
            "storage": "100Mi"
        },
        "nfs": {
            "server": "{}", // nfs server
            "path": "{}{}" // nfs path template: "{nfs-prefix}{path}"
        }
    }
}
```

matchPvcTemplate, this pvc contains a matchLabels field to match pv:  

```js
{
    "apiVersion": "v1",
    "kind": "PersistentVolumeClaim",
    "metadata": {
        "name": "pvc-{}-{}-{}", // pvc name template: "pvc-{tenant_id}-{username}-{tag}"
        "namespace": "{}", // pvc namespace template: "{namespace}"
    },
    "spec": {
        "accessModes": ["ReadWriteMany"],
        "storageClassName": "",
        "resources": {
            "requests": {
                "storage": "100Mi"
            }
        },
        "selector": {
            "matchLabels": {
                "pv": "pv-{}-{}-{}" // pv name template: "pv-{tenant_id}-{username}-{tag}"
            }
        }
    }
}
```

pvcTemplate:

```js
{
    "apiVersion": "v1",
    "kind": "PersistentVolumeClaim",
    "metadata": {
        "name": "pvc-{}-{}-{}", // pvc name template: "pvc-{tenant_id}-{useranme}-{tag}"
        "namespace": "{}", // pvc namespace template: "{namespace}"
    },
    "spec": {
        "accessModes": ["ReadWriteMany"],
        "storageClassName": "standard",
        "resources": {
            "requests": {
                "storage": "100Mi"
            }
        },
    }
}
```

## K8S namespace

**After creating tenant, please create a k8s namespace with tenant.id.**  

## envs

default ```env.sh```:  

```sh
export LOG_LEVEL=10 # debug
export TENANT_SERVICE_URL='http://192.168.0.48:7778/service/api/v1/tenants'
export NFS_SERVER="192.168.0.31"
export NFS_PREFIX="/nfs/"
```

## dev start

```sh
source ./env.sh
FLASK_APP=./volume-service.py flask run -h 0.0.0.0 -p 5010
```

## API

**Do NOT rely on returned value of POST APIs, K8S may return null if the resource couldn't be created in time!!!**  

### pv

pvInRequest:  

```js
{
    "tenant": ObjectID, // tenant id
    "username": String, // username,
    "tag": String, // pv tag, optional, defaults to 'default',
    "path": String, // pv path
}
```

pvInResponse (sample):  

```js
{'api_version': 'v1',
 'kind': 'PersistentVolume',
 'metadata': {'annotations': None,
              'cluster_name': None,
              'creation_timestamp': datetime.datetime(2019, 3, 13, 6, 38, 53, tzinfo=tzutc()),
              'deletion_grace_period_seconds': None,
              'deletion_timestamp': None,
              'finalizers': None,
              'generate_name': None,
              'generation': None,
              'initializers': None,
              'labels': {'pv': 'pv-test-script'},
              'name': 'pv-test-script',
              'namespace': None,
              'owner_references': None,
              'resource_version': None,
              'self_link': '/api/v1/persistentvolumes/pv-test-script',
              'uid': 'ab56e245-455a-11e9-bba7-0800277c8f39'},
 'spec': {'access_modes': ['ReadWriteMany'],
          'aws_elastic_block_store': None,
          'azure_disk': None,
          'azure_file': None,
          'capacity': {'storage': '100Mi'},
          'cephfs': None,
          'cinder': None,
          'claim_ref': None,
          'csi': None,
          'fc': None,
          'flex_volume': None,
          'flocker': None,
          'gce_persistent_disk': None,
          'glusterfs': None,
          'host_path': None,
          'iscsi': None,
          'local': None,
          'mount_options': None,
          'nfs': {'path': '/[nfs-prefix]/test-script',
                  'read_only': None,
                  'server': '[nfs-server]'},
          'node_affinity': None,
          'persistent_volume_reclaim_policy': 'Retain',
          'photon_persistent_disk': None,
          'portworx_volume': None,
          'quobyte': None,
          'rbd': None,
          'scale_io': None,
          'storage_class_name': None,
          'storageos': None,
          'volume_mode': 'Filesystem',
          'vsphere_volume': None},
 'status': {'message': None, 'phase': 'Pending', 'reason': None}}
```

| method | path | query | request | response | remark |
| ------ | ---- | ----- | ------- | -------- | ------ |
| POST | /pvs | | pvInRequest | pvInResponse | 创建PV |
| GET | /pvs | tenant, username, tag | | pvInResponse | 查询指定PV |
| DELETE | /pvs | tenant, username, tag | | | 删除指定PV |

### pvc

pvcInRequest:  

```js
{
    "tenant": ObjectID, // tenant id
    "username": String, // username
    "tag": String, // pvc tag, optional, defaults to 'default'
    "match": Boolean // create match pvc - a matchLabel field will be created to match pv, optional, defaults to False
}
```

pvcInResponse:  

```js
{'api_version': 'v1',
 'kind': 'PersistentVolumeClaim',
 'metadata': {'annotations': None,
              'cluster_name': None,
              'creation_timestamp': datetime.datetime(2019, 3, 14, 3, 47, 42, tzinfo=tzutc()),
              'deletion_grace_period_seconds': None,
              'deletion_timestamp': None,
              'finalizers': None,
              'generate_name': None,
              'generation': None,
              'initializers': None,
              'labels': None,
              'name': 'pvc-test-script',
              'namespace': 'jhub-46',
              'owner_references': None,
              'resource_version': None,
              'self_link': '/api/v1/namespaces/jhub-46/persistentvolumeclaims/pvc-test-script',
              'uid': 'ebcf82ca-460b-11e9-bba7-0800277c8f39'},
 'spec': {'access_modes': ['ReadWriteMany'],
          'data_source': None,
          'resources': {'limits': None, 'requests': {'storage': '100Mi'}},
          'selector': {'match_expressions': None, 'match_labels': None},
          'storage_class_name': 'standard',
          'volume_mode': 'Filesystem',
          'volume_name': None},
 'status': {'access_modes': None,
            'capacity': None,
            'conditions': None,
            'phase': 'Pending'}}
```

| method | path | query | request | response | remark |
| ------ | ---- | ----- | ------- | -------- | ------ |
| POST | /pvcs | | pvcInRequest | pvcInResponse | 创建PVC |
| GET | /pvcs | tenant, username, tag | | pvcInResponse | 查询指定PVC |
| DELETE | /pvcs | tenant, username, tag | | | 删除指定PVC |
