FROM debian:jessie

RUN apt-get update
RUN apt-get install -y python
RUN mkdir -p /data

VOLUME ["/data"]

WORKDIR /data

EXPOSE 8000

CMD [ "python", "-m", "SimpleHTTPServer", "8000" ]
