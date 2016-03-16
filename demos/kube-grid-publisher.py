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
import threading

import gcloud
import gcloud.pubsub
import requests

STATUS_MAP = {
    "Unknown": [63, 63, 63],
    "Pending": [63, 63, 0],
    "Running": [0, 63, 0],
    # "Terminating": [63, 0, 63],
    "Terminating": [63, 0, 0],
    "Error": [63, 0, 0],
}

FINISHED_STATES = (
    'Terminated',
    'Succeeded',
    'Failed',
)

finished = False
pod_map = collections.OrderedDict()


def blank_grid():
    grid = []
    for i in range(8):
        temp = []
        for j in range(8):
            temp.append((0,0,0))
        grid.append(temp)
    return grid

def get_pod_status(pod):
    """
    Gets the pod's status based on pod info. Looks at the pod's phase,
    state, deletionTimestamp to get the pod's status.

    Attempts to replicate the logic in kubectl that shows pod state.
    """
    reason = "Unknown"
    if pod["status"]["phase"]:
        reason = pod["status"]["phase"]
    for status in pod["status"].get("containerStatuses", []):
        if status["state"].get("waiting"):
            reason = "Pending"
        if status["state"].get("terminated"):
            reason = "Terminated"
    if pod["metadata"].get("deletionTimestamp"):
        reason = "Terminating"
    # TODO: Error?
    return reason

def parse_color(color_label):
    """
    Parses hex colors like FFFFFF into a list
    of 3 integer values representing red, green, and blue.
    """
    r = int(color_label[:2], 16)
    g = int(color_label[2:4], 16)
    b = int(color_label[4:6], 16)
    return [r, g, b]

def main():
    global finished

    parser = argparse.ArgumentParser(description="Kubernetes Grid Publisher")
    parser.add_argument('project', help="The Google Cloud Project")
    parser.add_argument('input_topic', help="The Google Cloud Pub/Sub Topic used for input")
    parser.add_argument('output_topic', help="The Google Cloud Pub/Sub Topic used for output")

    parser.add_argument('--subscription', help="The Google Cloud Pub/Sub Subscription", default="kube-grid-publisher-" + str(int(time.time())))
    parser.add_argument('--server', help="The Kubernetes API server", default="localhost:8001")

    args = parser.parse_args()

    p = threading.Thread(target=publisher, args=(args.server, args.project, args.output_topic))
    s = threading.Thread(target=subscriber, args=(args.server, args.project, args.input_topic, args.subscription))

    p.start()
    s.start()


    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            finished = True
            print("Exiting...")
            p.join()
            s.join()
            return

def subscriber(api_host, project_name, topic_name, subscription_name=None):
    client = gcloud.pubsub.Client(project=project_name)
    topic = gcloud.pubsub.Topic(topic_name, client)
    subscription = gcloud.pubsub.Subscription(subscription_name, topic)

    try:
        subscription.create()
    except gcloud.exceptions.Conflict:
        pass

    print('Listening to topic "%s" on subscription "%s"...' % (topic.name, subscription.name))
    while not finished:
        time.sleep(0.5)
        messages = subscription.pull(return_immediately=True)  # TODO - set max_messages higher 
        for ackid, message in messages:
            event = json.loads(message.data)
            x = event["X"] - 1
            y = event["Y"] - 1
            nodes = pod_map.items()
            if x < len(nodes):
                pods = nodes[x][1]
                if y < len(pods):
                    pod_name = pods[y]["metadata"]["name"]

                    # Kill some pods
                    print('Deleting pod "%s"...' % pod_name)
                    resp = requests.delete(
                        'http://{server}/api/v1/namespaces/{namespace}/pods/{name}'.format(
                            server=api_host,
                            namespace='default',
                            name=pod_name,
                        ),
                    )

            subscription.acknowledge(ackid)

def publisher(api_host, project_name, topic_name):
    global pod_map

    client = gcloud.pubsub.Client(project=project_name)
    topic = gcloud.pubsub.Topic(topic_name, client)
    try:
        topic.create()
    except gcloud.exceptions.Conflict:
        pass

    last_grid = None

    print('Publishing cluster info to topic "%s"...' % topic.name)
    while not finished:
        time.sleep(1)
        try:
            nodes_json = requests.get("http://{server}/api/v1/nodes".format(server=api_host)).json()
            nodes = [n["metadata"]["name"] for n in nodes_json["items"]]
            nodes.sort()

            pod_map = collections.OrderedDict()
            for node in nodes:
                pod_map[node] = []

            g = blank_grid()
            pods_json = requests.get("http://{server}/api/v1/namespaces/default/pods".format(server=api_host)).json()
            for p in pods_json["items"]:
                # Only report pods that are assigned to a node.
                if "nodeName" in p["spec"]:
                    if p["metadata"]["labels"].get("visualize", "false").lower() == "true":
                        pod_map[p["spec"]["nodeName"]].append(p)

            for x, n in enumerate(nodes[:8]):
                for y, p in enumerate(pod_map.get(n, [])[:8]):
                    status = get_pod_status(p)

                    # Don't show pods who have completed.
                    # TODO: Maybe turn this into an option?
                    if status not in FINISHED_STATES:
                        if status == "Running":
                            color_label = p["metadata"]["labels"].get("color")
                            if color_label:
                                g[x][y] = parse_color(color_label)
                            else:
                                g[x][y] = STATUS_MAP[status]
                        else:
                            g[x][y] = STATUS_MAP[status]

            # Only publish to the topic if the grid data has changed.
            if g != last_grid:
                for unused, n in enumerate(nodes):
                    print n, len(pod_map.get(n, []))
                print
                data = json.dumps(g)
                topic.publish(data)
            last_grid = g

        except Exception as e:
            logging.error(traceback.format_exc())

if __name__ == '__main__':
    main()
