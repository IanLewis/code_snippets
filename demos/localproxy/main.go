package main

import (
	"flag"
	"log"
	"net/http"
	"net/http/httputil"
	"os"

	"github.com/gorilla/handlers"
)

var (
	addr = flag.String("addr", ":8080", "HTTP listen address")
	to   = flag.String("to", "localhost:8001", "HTTP forward to address")
)

// A simple io.Writer wrapper around a logger so that we can use
// the logger as an io.Writer
type LogWriter struct{ *log.Logger }

func (w LogWriter) Write(b []byte) (int, error) {
	w.Printf("%s", b)
	return len(b), nil
}

func main() {
	flag.Parse()

	var h http.Handler
	h = &httputil.ReverseProxy{
		Director: func(req *http.Request) {
			req.URL.Scheme = "http"
			req.URL.Host = *to
		},
	}

	l := log.New(os.Stdout, "", 0)
	h = handlers.CombinedLoggingHandler(LogWriter{l}, h)

	http.Handle("/", h)
	http.ListenAndServe(*addr, nil)
}
