# Testing Guide

## Local Development Testing

### 1. Start the Server

**Using Docker:**
```bash
docker-compose up
```

**Manual:**
```bash
./scripts/setup.sh
./scripts/start-dev.sh
```

### 2. Test API Endpoints

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Register a Test Device
```bash
curl -X POST http://localhost:8000/api/v1/devices/register \
  -H "Content-Type: application/json" \
  -d '{
    "hardware_id": "test-hw-001",
    "controller_id": "TEST-GATE-001",
    "firmware_version": "1.0.0",
    "device_name": "Test Gate"
  }'
```

Save the response - you'll need the MQTT credentials.

#### Authorize a Test User
```bash
curl -X POST http://localhost:8000/api/v1/users/authorize \
  -H "Content-Type: application/json" \
  -d '{
    "controller_id": "TEST-GATE-001",
    "user_token": "test-user-token-123",
    "access_level": "owner"
  }'
```

#### Discover Devices
```bash
curl -X POST http://localhost:8000/api/v1/users/discover \
  -H "Content-Type: application/json" \
  -d '{
    "user_token": "test-user-token-123"
  }'
```

#### Send Command
```bash
curl -X POST http://localhost:8000/api/v1/commands/send \
  -H "Content-Type: application/json" \
  -d '{
    "controller_id": "TEST-GATE-001",
    "user_token": "test-user-token-123",
    "command": {
      "action": "open_gate",
      "gate_number": 1
    }
  }'
```

### 3. Test MQTT

#### Monitor All Topics
```bash
# Terminal 1 - Subscribe to all topics
mosquitto_sub -h localhost -t 'gatetorio/#' -v
```

#### Simulate Pi Publishing Status
```bash
# Terminal 2 - Publish status update
mosquitto_pub -h localhost -t 'gatetorio/TEST-GATE-001/status' \
  -m '{"status": "online", "gate_state": "closed"}'
```

#### Use Test Script
```bash
python scripts/test-mqtt.py localhost 1883
```

### 4. Test Sharing Tokens

#### Create Sharing Token
```bash
curl -X POST http://localhost:8000/api/v1/sharing/create \
  -H "Content-Type: application/json" \
  -d '{
    "controller_id": "TEST-GATE-001",
    "user_token": "test-user-token-123",
    "access_level": "engineer",
    "expires_in_hours": 24,
    "notes": "Test token"
  }'
```

Save the token from the response.

#### Redeem Sharing Token
```bash
curl -X POST http://localhost:8000/api/v1/sharing/redeem \
  -H "Content-Type: application/json" \
  -d '{
    "token": "YOUR_TOKEN_HERE",
    "user_token": "new-user-token-456"
  }'
```

## Integration Testing

### Simulating Pi Device

Create `test_pi_client.py`:
```python
import requests
import paho.mqtt.client as mqtt
import json
import time

# Configuration
API_BASE = "http://localhost:8000/api/v1"
HARDWARE_ID = "test-pi-001"
CONTROLLER_ID = "TEST-GATE-PI"

def register_device():
    """Register device with server"""
    response = requests.post(f"{API_BASE}/devices/register", json={
        "hardware_id": HARDWARE_ID,
        "controller_id": CONTROLLER_ID,
        "firmware_version": "1.0.0",
        "device_name": "Test Pi Gate"
    })
    return response.json()

def on_connect(client, userdata, flags, rc):
    """MQTT connect callback"""
    print(f"Connected to MQTT broker: {rc}")
    client.subscribe(f"gatetorio/{CONTROLLER_ID}/commands")
    print(f"Subscribed to commands topic")

def on_message(client, userdata, msg):
    """MQTT message callback"""
    print(f"\nReceived command: {msg.topic}")
    command = json.loads(msg.payload.decode())
    print(json.dumps(command, indent=2))

    # Simulate processing and send status
    status = {
        "status": "command_executed",
        "command": command,
        "result": "success"
    }
    client.publish(f"gatetorio/{CONTROLLER_ID}/status", json.dumps(status))

def main():
    # Register device
    print("Registering device...")
    reg_data = register_device()
    print(f"Device registered: {reg_data['controller_id']}")

    # Connect to MQTT
    client = mqtt.Client(client_id=f"pi_{CONTROLLER_ID}")
    client.on_connect = on_connect
    client.on_message = on_message

    # Use credentials from registration
    if reg_data.get('mqtt_username'):
        client.username_pw_set(
            reg_data['mqtt_username'],
            reg_data['mqtt_password']
        )

    print("Connecting to MQTT broker...")
    client.connect(reg_data['mqtt_broker_host'], reg_data['mqtt_broker_port'])

    # Start loop
    client.loop_start()

    # Publish periodic status updates
    try:
        while True:
            status = {
                "status": "online",
                "timestamp": time.time(),
                "gates": {"gate1": "closed"}
            }
            client.publish(
                f"gatetorio/{CONTROLLER_ID}/status",
                json.dumps(status)
            )
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nShutting down...")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
```

Run:
```bash
python test_pi_client.py
```

### Simulating App

Create `test_app_client.py`:
```python
import requests
import paho.mqtt.client as mqtt
import json

# Configuration
API_BASE = "http://localhost:8000/api/v1"
USER_TOKEN = "test-app-user-001"
CONTROLLER_ID = "TEST-GATE-PI"

def authorize_user():
    """Authorize user (normally done by Pi after BLE pairing)"""
    response = requests.post(f"{API_BASE}/users/authorize", json={
        "controller_id": CONTROLLER_ID,
        "user_token": USER_TOKEN,
        "access_level": "owner"
    })
    return response.json()

def discover_devices():
    """Discover accessible devices"""
    response = requests.post(f"{API_BASE}/users/discover", json={
        "user_token": USER_TOKEN
    })
    return response.json()

def send_command(command):
    """Send command to device"""
    response = requests.post(f"{API_BASE}/commands/send", json={
        "controller_id": CONTROLLER_ID,
        "user_token": USER_TOKEN,
        "command": command
    })
    return response.json()

def on_message(client, userdata, msg):
    """MQTT message callback"""
    print(f"\nReceived status update:")
    status = json.loads(msg.payload.decode())
    print(json.dumps(status, indent=2))

def main():
    # Authorize user (simulate BLE pairing)
    print("Authorizing user...")
    auth = authorize_user()
    print(f"User authorized: {auth}")

    # Discover devices
    print("\nDiscovering devices...")
    devices = discover_devices()
    print(f"Found {len(devices['devices'])} device(s)")
    for device in devices['devices']:
        print(f"  - {device['device_name']} ({device['controller_id']})")

    # Subscribe to status updates
    client = mqtt.Client(client_id=f"app_{USER_TOKEN}")
    client.on_message = on_message
    client.connect("localhost", 1883)
    client.subscribe(f"gatetorio/{CONTROLLER_ID}/status")
    client.loop_start()
    print(f"\nSubscribed to status updates")

    # Send test command
    print("\nSending test command...")
    command = {"action": "open_gate", "gate_number": 1}
    result = send_command(command)
    print(f"Command result: {result}")

    # Keep listening for status
    try:
        print("\nListening for status updates (Ctrl+C to exit)...")
        while True:
            pass
    except KeyboardInterrupt:
        print("\nShutting down...")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
```

Run:
```bash
python test_app_client.py
```

## Complete Test Workflow

1. **Start server** (Terminal 1):
   ```bash
   docker-compose up
   ```

2. **Monitor MQTT** (Terminal 2):
   ```bash
   python scripts/test-mqtt.py
   ```

3. **Start Pi simulator** (Terminal 3):
   ```bash
   python test_pi_client.py
   ```

4. **Start App simulator** (Terminal 4):
   ```bash
   python test_app_client.py
   ```

You should see:
- Pi registers and connects to MQTT
- App authorizes and discovers device
- App sends command via API
- Command flows through MQTT to Pi
- Pi responds with status
- App receives status update

## API Documentation

Access auto-generated API docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Troubleshooting Tests

### Server won't start
```bash
# Check logs
docker-compose logs -f api

# Check database
ls -la gatetorio.db
```

### MQTT connection fails
```bash
# Test broker directly
mosquitto_pub -h localhost -t test -m "test"

# Check broker logs
docker-compose logs -f mosquitto
```

### API returns 500 errors
```bash
# Check server logs
docker-compose logs api

# Check database connection
docker-compose exec api python -c "from app.core.database import init_db; import asyncio; asyncio.run(init_db())"
```
