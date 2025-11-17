"""MQTT client service for device communication"""

import asyncio
import json
import logging
from typing import Callable, Dict, Optional
import paho.mqtt.client as mqtt
from app.core.config import settings

logger = logging.getLogger(__name__)


class MQTTService:
    """
    MQTT client service for handling device communication
    Topics:
    - gatetorio/{controller_id}/commands - Commands from app to Pi
    - gatetorio/{controller_id}/status - Status updates from Pi to app
    """

    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.message_callbacks: Dict[str, Callable] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def initialize(self):
        """Initialize MQTT client"""
        self.client = mqtt.Client(client_id="gatetorio_server", protocol=mqtt.MQTTv311)

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Set credentials if provided
        if settings.MQTT_BROKER_USERNAME:
            self.client.username_pw_set(
                settings.MQTT_BROKER_USERNAME, settings.MQTT_BROKER_PASSWORD
            )

        logger.info(
            f"MQTT client initialized for broker {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}"
        )

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")

            # Subscribe to all status topics (for monitoring)
            topic = f"{settings.MQTT_TOPIC_PREFIX}/+/status"
            client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when client disconnects from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8")

            logger.debug(f"Received message on {topic}: {payload}")

            # Parse topic to get controller_id
            parts = topic.split("/")
            if len(parts) >= 3:
                controller_id = parts[1]
                message_type = parts[2]

                # Call registered callbacks
                callback_key = f"{controller_id}/{message_type}"
                if callback_key in self.message_callbacks:
                    self.message_callbacks[callback_key](controller_id, payload)

                # Call wildcard callbacks
                if f"*/{message_type}" in self.message_callbacks:
                    self.message_callbacks[f"*/{message_type}"](controller_id, payload)

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                keepalive=60,
            )
            self.client.loop_start()
            logger.info("MQTT client connection started")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")

    def publish_command(
        self, controller_id: str, command: dict, qos: int = 1
    ) -> bool:
        """
        Publish a command to a device
        Args:
            controller_id: Target device controller ID
            command: Command dictionary to send
            qos: Quality of service (0, 1, or 2)
        Returns:
            True if published successfully
        """
        if not self.connected:
            logger.error("MQTT client not connected")
            return False

        try:
            topic = f"{settings.MQTT_TOPIC_PREFIX}/{controller_id}/commands"
            payload = json.dumps(command)

            result = self.client.publish(topic, payload, qos=qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published command to {topic}: {command}")
                return True
            else:
                logger.error(f"Failed to publish command: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Error publishing command: {e}")
            return False

    def subscribe_to_device(self, controller_id: str, callback: Callable):
        """
        Subscribe to status updates from a specific device
        Args:
            controller_id: Device controller ID
            callback: Function to call when status is received
        """
        topic = f"{settings.MQTT_TOPIC_PREFIX}/{controller_id}/status"
        self.client.subscribe(topic)

        # Register callback
        callback_key = f"{controller_id}/status"
        self.message_callbacks[callback_key] = callback

        logger.info(f"Subscribed to {topic}")

    def register_callback(self, message_type: str, callback: Callable):
        """
        Register a callback for all devices of a specific message type
        Args:
            message_type: Type of message (e.g., "status", "commands")
            callback: Function to call when message is received
        """
        callback_key = f"*/{message_type}"
        self.message_callbacks[callback_key] = callback
        logger.info(f"Registered callback for all devices: {message_type}")


# Global MQTT service instance
mqtt_service = MQTTService()
