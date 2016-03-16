package main

import (
	"encoding/json"
	"flag"
	"log"
	"time"

	"golang.org/x/net/context"

	"google.golang.org/cloud"
	"google.golang.org/cloud/internal/transport"
	"google.golang.org/cloud/pubsub"

	lc "github.com/IanLewis/launchcontrol"
	"github.com/rakyll/portmidi"
)

var (
	project = flag.String("project", "", "The name of the project.")
	topic   = flag.String("topic", "", "The Cloud Pub/Sub topic to listen on.")
)

const prodAddr = "https://pubsub.googleapis.com/"
const userAgent = "gcloud-golang-pubsub/20151008"

func newContext() context.Context {
	// Set up client options
	o := []cloud.ClientOption{
		cloud.WithEndpoint(prodAddr),
		cloud.WithScopes(pubsub.ScopePubSub, pubsub.ScopeCloudPlatform),
		cloud.WithUserAgent(userAgent),
	}

	// Create an authenticated HTTP client and context
	client, _, err := transport.NewHTTPClient(context.Background(), o...)
	if err != nil {
		log.Fatal(err)
	}
	ctx := cloud.NewContext(*project, client)
	return ctx
}

type Event struct {
	Control int   `json:"control"`
	X       int   `json:"x"`
	Value   int64 `json:"value"`
}

type EventChannel struct {
	ctx context.Context
	c   chan Event
}

func (e *EventChannel) Run() {
	for {
		// Block for an event when we have no event queued.
		event := <-e.c

	L:
		// We have an event but we'll only send it if there is
		// no other event for 500ms.
		for {
			select {
			case e2 := <-e.c:
				event = e2
			case <-time.After(500 * time.Millisecond):
				// No event has happened for 500ms
				// Send the event via pubsub
				log.Println(event)
				b, err := json.Marshal(&event)
				if err != nil {
					log.Println(err)
					continue
				}
				pubsub.Publish(e.ctx, *topic, &pubsub.Message{
					Data: b,
				})
				// break L is necessary so that we can break out
				// of the for loop and not just the select block.
				break L
			}
		}
	}
}

var eventChannels = make(map[int]map[int]*EventChannel)

func main() {
	flag.Parse()

	ctx := newContext()

	err := portmidi.Initialize()
	if err = portmidi.Initialize(); err != nil {
		log.Fatal("error while initializing portmidi", err)
	}
	defer portmidi.Terminate()

	c, err := lc.Open()
	if err != nil {
		log.Fatal(err)
	}
	defer func() {
		c.Close()
	}()

	c.Reset()

	log.Printf("Publishing Launch Control input to topic \"%s\"...", *topic)

	ch := c.Listen()
	for {
		// Wait for events from the Launch Control
		event := <-ch
		e := Event{
			Control: event.Control,
			X:       event.X,
			Value:   event.Value,
		}

		// Create a new channel for the control if it doesn't exist yet.
		if _, ok := eventChannels[event.Control]; !ok {
			eventChannels[event.Control] = make(map[int]*EventChannel)
		}
		if _, ok := eventChannels[event.Control][event.X]; !ok {
			eventChannels[event.Control][event.X] = &EventChannel{
				ctx: ctx,
				c:   make(chan Event),
			}
			go eventChannels[event.Control][event.X].Run()
		}

		// Send the event we got to that control's channel.
		eventChannels[event.Control][event.X].c <- e
	}

	c.Close()
}
