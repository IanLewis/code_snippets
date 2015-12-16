# Test script to get several urls in parallel

import asyncio


class Request(object):
    def __init__(self, method, path, headers, body):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body


class Response(object):
    CODES = {
        200: "OK",
        404: "Not Found",
    }

    def __init__(self, body, code=200,
                 encoding='utf-8', content_type='text/html'):
        self.code = code
        self.body = body
        self.encoding = encoding
        self.content_type = content_type

    @property
    def codestr(self):
        return self.CODES[self.code]

    def asbytes(self):
        return b"\r\n\r\n".join([
            bytes(
                "\r\n".join([
                    "HTTP/1.1 {code} {codestr}",
                    "Content-Type: {type}; charset={encoding}",
                    "Content-Length: {len}",
                ]).format(
                    code=self.code,
                    codestr=self.codestr,
                    type=self.content_type,
                    encoding=self.encoding.upper(),
                    len=len(self.body),
                ),
                self.encoding,
            ),
            bytes(self.body, self.encoding),
        ])


class SimpleHTTPProtocol(asyncio.Protocol):

    routes = {
        '/': 'home',
        '/hello': 'hello',
    }

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        message = data.decode()
        header_lines = message.split("\r\n\r\n")[0].split("\r\n")
        method, path, protocol = header_lines[0].split(" ")
        body = ""

        headers = {}
        for line in header_lines[1:]:
            name, val = line.split(": ", 1)
            headers[name] = val

        req = Request(method, path, headers, body)
        if req.path in self.routes:
            handler = getattr(self, self.routes[req.path])
            resp = handler(req)
        else:
            resp = Response("Not Found", 404)

        self.transport.write(resp.asbytes())
        self.transport.close()
        print("{} {} {}".format(req.method, req.path, resp.code))

    def home(self, req):
        return Response("""<a href="/hello">Say Hello</a>""")

    def hello(self, req):
        return Response("""Howdy!!""")


loop = asyncio.get_event_loop()
server = loop.run_until_complete(
    loop.create_server(SimpleHTTPProtocol, '127.0.0.1', 8000))

# Serve requests until Ctrl+C is pressed
print('Serving on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
