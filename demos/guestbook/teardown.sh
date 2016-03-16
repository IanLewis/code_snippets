#!/bin/sh
kubectl delete rc frontend-2
kubectl delete rc frontend-3
kubectl delete svc frontend
kubectl delete rc redis-master
kubectl delete svc redis-master
kubectl delete rc redis-slave
kubectl delete svc redis-slave
