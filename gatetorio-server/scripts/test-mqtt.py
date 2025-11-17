#!/usr/bin/env python3
"""Simple MQTT test script"""

import paho.mqtt.client as mqtt
import json
import time
import sys


def on_connect(client, userdata, flags, rc):
    """Callback for when client connects"""
    if rc == 0:
        print("Connected to MQTT broker")
        # Subscribe to all gatetorio topics
        client.subscribe("gatetorio/#")
        print("Subscribed to gatetorio/#")
    else:
        print(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """Callback for when a message is received"""
    print(f"\n[{msg.topic}]")
    try:
        payload = json.loads(msg.payload.decode())
        print(json.dumps(payload, indent=2))
    except:
        print(msg.payload.decode())


def main():
    """Main function"""
    broker = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 1883

    print(f"Connecting to MQTT broker at {broker}:{port}...")

    client = mqtt.Client(client_id="gatetorio_test")
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker, port, 60)
        client.loop_start()

        print("\nListening for messages (Ctrl+C to exit)...")
        print("You can test by publishing to topics like:")
        print(f"  mosquitto_pub -h {broker} -t gatetorio/test_device/status -m '{{\"status\": \"online\"}}'")
        print()

        # Keep running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
