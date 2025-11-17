# Gatetorio Server API Documentation

Base URL: `http://gates.stoner.team/api/v1`

## Authentication

Currently using simple token-based authentication with user tokens from BLE pairing.

## Device Management

### Register Device
**POST** `/devices/register`

Register a new device or update existing device on boot.

**Request Body:**
```json
{
  "hardware_id": "b8:27:eb:12:34:56",
  "controller_id": "GATE-001",
  "firmware_version": "1.0.0",
  "device_name": "Main Gate"
}
```

**Response:**
```json
{
  "device_id": 1,
  "controller_id": "GATE-001",
  "mqtt_username": "device_GATE-001",
  "mqtt_password": "generated_password",
  "mqtt_broker_host": "gates.stoner.team",
  "mqtt_broker_port": 1883,
  "mqtt_topic_commands": "gatetorio/GATE-001/commands",
  "mqtt_topic_status": "gatetorio/GATE-001/status"
}
```

### Get Device Info
**GET** `/devices/{controller_id}`

Get device information.

**Response:**
```json
{
  "id": 1,
  "controller_id": "GATE-001",
  "hardware_id": "b8:27:eb:12:34:56",
  "device_name": "Main Gate",
  "firmware_version": "1.0.0",
  "is_online": true,
  "last_seen": "2025-11-17T20:00:00Z",
  "created_at": "2025-11-01T10:00:00Z"
}
```

### Device Heartbeat
**POST** `/devices/{controller_id}/heartbeat`

Update device last_seen timestamp (called periodically by Pi).

**Response:**
```json
{
  "status": "ok",
  "last_seen": "2025-11-17T20:00:00Z"
}
```

## User Authorization

### Authorize User
**POST** `/users/authorize`

Authorize a user to access a device (called by Pi after BLE pairing).

**Request Body:**
```json
{
  "controller_id": "GATE-001",
  "user_token": "user_token_from_ble_pairing",
  "access_level": "owner"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User authorized successfully",
  "user_id": 1
}
```

### Discover Devices
**POST** `/users/discover`

Discover devices accessible to a user (called by app).

**Request Body:**
```json
{
  "user_token": "user_token_from_ble_pairing"
}
```

**Response:**
```json
{
  "devices": [
    {
      "id": 1,
      "controller_id": "GATE-001",
      "hardware_id": "b8:27:eb:12:34:56",
      "device_name": "Main Gate",
      "firmware_version": "1.0.0",
      "is_online": true,
      "last_seen": "2025-11-17T20:00:00Z",
      "created_at": "2025-11-01T10:00:00Z"
    }
  ]
}
```

### Check Access
**GET** `/users/access/{user_token}/{controller_id}`

Check if a user has access to a device.

**Response:**
```json
{
  "has_access": true,
  "access_level": "owner",
  "expires_at": null
}
```

## Sharing Tokens

### Create Sharing Token
**POST** `/sharing/create`

Create a sharing token for engineer handoff (owner only).

**Request Body:**
```json
{
  "controller_id": "GATE-001",
  "user_token": "owner_token",
  "access_level": "engineer",
  "expires_in_hours": 24,
  "notes": "Handoff to John for installation"
}
```

**Response:**
```json
{
  "token": "generated_sharing_token",
  "expires_at": "2025-11-18T20:00:00Z",
  "controller_id": "GATE-001"
}
```

### Redeem Sharing Token
**POST** `/sharing/redeem`

Redeem a sharing token to gain access.

**Request Body:**
```json
{
  "token": "generated_sharing_token",
  "user_token": "new_user_token"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Access granted successfully",
  "device_info": {
    "id": 1,
    "controller_id": "GATE-001",
    "device_name": "Main Gate",
    "is_online": true
  }
}
```

### List Sharing Tokens
**GET** `/sharing/tokens/{controller_id}?user_token=owner_token`

List all sharing tokens for a device (owner only).

**Response:**
```json
{
  "tokens": [
    {
      "token": "abc12345...",
      "access_level": "engineer",
      "is_used": false,
      "expires_at": "2025-11-18T20:00:00Z",
      "created_at": "2025-11-17T20:00:00Z",
      "notes": "Handoff to John"
    }
  ]
}
```

## Commands

### Send Command
**POST** `/commands/send`

Send a command to a device via MQTT.

**Request Body:**
```json
{
  "controller_id": "GATE-001",
  "user_token": "user_token",
  "command": {
    "action": "open_gate",
    "gate_number": 1
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Command sent successfully"
}
```

### Get Device Status
**GET** `/commands/status/{controller_id}?user_token=user_token`

Get current device status.

**Response:**
```json
{
  "controller_id": "GATE-001",
  "is_online": true,
  "last_seen": "2025-11-17T20:00:00Z",
  "firmware_version": "1.0.0"
}
```

## Health Check

### Health
**GET** `/health`

Check server health status.

**Response:**
```json
{
  "status": "healthy",
  "mqtt_connected": true,
  "database_connected": true,
  "version": "0.1.0"
}
```

## MQTT Topics

### Command Topic
`gatetorio/{controller_id}/commands`

App publishes commands here, Pi subscribes.

**Example Message:**
```json
{
  "action": "open_gate",
  "gate_number": 1,
  "timestamp": "2025-11-17T20:00:00Z"
}
```

### Status Topic
`gatetorio/{controller_id}/status`

Pi publishes status here, App subscribes.

**Example Message:**
```json
{
  "status": "online",
  "gate_states": {
    "gate1": "closed",
    "gate2": "open"
  },
  "timestamp": "2025-11-17T20:00:00Z"
}
```

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message here"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad request
- `403` - Forbidden (no access)
- `404` - Not found
- `500` - Server error
- `503` - Service unavailable (device offline)

## Example Workflows

### Initial Pi Setup
1. Pi boots up
2. Pi calls `/devices/register` with hardware_id and controller_id
3. Server returns MQTT credentials
4. Pi connects to MQTT broker
5. Pi subscribes to command topic

### User Pairing via BLE
1. User opens app, pairs via BLE
2. Pi receives user token from app
3. Pi calls `/users/authorize` with controller_id and user_token
4. Server stores authorization
5. User can now discover device remotely

### Remote Command
1. App calls `/users/discover` to get accessible devices
2. User selects device
3. App calls `/commands/send` with command
4. Server publishes to MQTT topic
5. Pi receives and executes command
6. Pi publishes status update
7. App receives status via MQTT

### Engineer Handoff
1. Owner calls `/sharing/create` to generate token
2. Owner shares token with engineer (text, QR code, etc.)
3. Engineer calls `/sharing/redeem` with their user_token
4. Engineer now has access to device
5. Token is marked as used
