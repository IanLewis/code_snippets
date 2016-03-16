# Kubernetes Cockpit Demo

This is a project for hardware interfaces to the Kubernetes API. Hardware
interfaces are implemented in the 'hwagents' folder and generally poll
a Cloud PubSub topic for data published from a separate app.

# Setup

TODO: Go related setup

$ sudo apt-get update
$ sudo apt-get install python-dev libffi-dev libssl-dev
$ virtalenv venv
$ ./venv/bin/pip install -r requirements.txt

# Kubectl API demo

There is a local kubectl API demo that can be done locally. Use two terminals
to start up kubectl and run the localproxy app. Localproxy is a local logging
http reverse proxy that can be used to show the API calls that kubectl is
making.

```
$ kubectl proxy
```

Localproxy listens on :8080 by default.

```
$ go run localproxy/main.go
```

Now you can run kubectl and look at the output.

```
$ kubectl get pods -s http://localhost:8080
NAME                 READY     STATUS    RESTARTS   AGE
ingestmaster-xl8iq   1/1       Running   0          5h
```

Something like the following should show up in the localproxy output.

```
127.0.0.1 - - [29/Feb/2016:18:25:59 +0900] "GET /api HTTP/1.1" 200 57 "" "kubectl/v1.1.7 (linux/amd64) kubernetes/e4e6878"
127.0.0.1 - - [29/Feb/2016:18:25:59 +0900] "GET /api/v1/namespaces/default/pods HTTP/1.1" 200 2134 "" "kubectl/v1.1.7 (linux/amd64) kubernetes/e4e6878"
```

# Cockpit Demo

## LaunchPad MK2

The launchpad mk2 agent is located in hwagents/launchpad. It takes messages
over PubSub that contain information on how to set up the color grid. It requires
the github.com/IanLewis/launchpad package.

Homepage: https://global.novationmusic.com/launch/launchpad#
Programmer's Reference: https://global.novationmusic.com/sites/default/files/novation/downloads/10529/launchpad-mk2-programmers-reference-guide_0.pdf

## Launch Control XL

Homepage: https://global.novationmusic.com/launch/launch-control-xl
Programmer's Reference: https://global.novationmusic.com/sites/default/files/novation/downloads/9922/launch-control-xl-programmers-reference-guide.pdf

