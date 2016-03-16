/*
Copyright 2016 Google Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

// The launchpad hardware agent pulls messages from Cloud Pub/Sub
// and applies them to the launchpad board.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"strconv"
	"time"

	"golang.org/x/net/context"

	"google.golang.org/cloud/pubsub"

	"github.com/IanLewis/launchpad/mk2"
	"github.com/rakyll/portmidi"
)

var (
	project      = flag.String("project", "", "The name of the project.")
	inputTopic   = flag.String("input_topic", "", "The Cloud Pub/Sub topic to listen on for input.")
	outputTopic  = flag.String("output_topic", "", "The Cloud Pub/Sub topic to listen on for output.")
	subscription = flag.String("subscription", "", "The subcription to use. A new one is created by default.")
)

const prodAddr = "https://pubsub.googleapis.com/"
const userAgent = "gcloud-golang-pubsub/20151008"

func main() {
	flag.Parse()

	client, err := pubsub.NewClient(context.Background(), *project)
	if err != nil {
		log.Fatal(err)
	}

	// Set up the subscription
	topic := client.Topic(*outputTopic)
	var sub *pubsub.SubscriptionHandle
	if *subscription == "" {
		subName := fmt.Sprintf("launchpad-agent-%s", strconv.FormatInt(time.Now().Unix(), 10))
		subscription = &subName
		sub, err = topic.Subscribe(context.Background(), *subscription, 300*time.Second, nil)
		if err != nil {
			log.Fatal(err)
		}
	} else {
		sub = client.Subscription(*subscription)
	}

	err = portmidi.Initialize()
	if err = portmidi.Initialize(); err != nil {
		log.Fatal("error while initializing portmidi", err)
	}

	defer portmidi.Terminate()

	pad, err := mk2.Open()
	if err != nil {
		log.Fatal(err)
	}

	// Reset the pad and make sure it's clear
	pad.Reset()
	defer pad.Reset()

	// Listen to input in the background
	go func() {
		log.Printf("Publishing LaunchPad input to topic \"%s\"...", *inputTopic)
		topic := client.Topic(*inputTopic)
		ch := pad.Listen()
		for {
			hit := <-ch
			b, err := json.Marshal(&hit)
			if err != nil {
				log.Println(err)
				continue
			}
			_, err = topic.Publish(context.Background(), &pubsub.Message{
				Data: b,
			})
			if err != nil {
				log.Println(err)
			}
		}
	}()

	log.Printf("Listening to topic %s on subscription %s...", *outputTopic, *subscription)

	var grid [][][]int
	for {
		msgs, err := sub.Pull(context.Background(), 0)
		if err != nil {
			log.Println(err)
			time.Sleep(10 * time.Millisecond)
			continue
		}

		for {
			m, err := msgs.Next()
			if err != nil {
				log.Println(err)
				time.Sleep(10 * time.Millisecond)
				break
			}

			err = json.Unmarshal(m.Data, &grid)
			if err != nil {
				log.Println(err)
				continue
			}
			log.Println(m.ID, m.AckID)

			// Light the right buttons.
			// Make sure the pad is reset.
			pad.Reset()
			for x, col := range grid {
				for y, cell := range col {
					pad.Light(x+1, y+1, cell[0], cell[1], cell[2])
				}
			}

			// Ack the message in the background.
			m.Done(true)
		}
	}
}
