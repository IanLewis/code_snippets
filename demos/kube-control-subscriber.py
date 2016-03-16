# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# 	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import collections
import json
import logging
import time
import traceback

import gcloud
import gcloud.pubsub
import requests

def main():
    parser = argparse.ArgumentParser(description="Kubernetes Control Subscriber")
    parser.add_argument('project', help="The Google Cloud Project")
    parser.add_argument('topic', help="The Google Cloud Pub/Sub Topic")
    parser.add_argument('rc', nargs='+', help="The replication controller to scale")
    parser.add_argument('--subscription', help="The Google Cloud Pub/Sub Subscription", default="kube-control-subscriber-" + str(int(time.time())))
    parser.add_argument('--server', help="The Kubernetes API server", default="localhost:8001")

    args = parser.parse_args()

    client = gcloud.pubsub.Client(project=args.project)
    topic = gcloud.pubsub.Topic(args.topic, client)
    subscription = gcloud.pubsub.Subscription(args.subscription, topic)
    try:
        subscription.create()
    except gcloud.exceptions.Conflict:
        pass

    if len(args.rc) > 8:
        print("Too many replication controllers.")
        return

    print('Listening to topic "%s" on subscription "%s"...' % (topic.name, subscription.name))
    while True:
        try:
            messages = subscription.pull()  # TODO - set max_messages higher 
            for ackid, message in messages:
                event = json.loads(message.data)
                if event["control"] == 3:
                    if event["x"] >= len(args.rc):
                        continue

                    rc = args.rc[event["x"]]

                    replicas = int(event["value"] / 3)
                    print("Scaling %s to %s replicas..." % (rc, replicas))
                    
                    # Scale the replication controllers using a merge patch
                    # See: http://kubernetes.io/v1.1/docs/devel/api-conventions.html#patch-operations
                    resp = requests.patch(
                        'http://{server}/api/v1/namespaces/{namespace}/replicationcontrollers/{name}'.format(
                            server=args.server,
                            namespace='default',
                            name=rc,
                        ),
                        json={"spec": {"replicas": replicas}},
                        headers={
                            "Content-Type": "application/merge-patch+json",
                            "Accept": "application/json",
                        }
                    )
                    if resp.status_code >= 300:
                        print("Error response: %s" % resp)
                subscription.acknowledge(ackid)
        except KeyboardInterrupt:
            print("Exiting...")
            break


if __name__ == '__main__':
    main()
