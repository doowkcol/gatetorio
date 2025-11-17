# Gatetorio Central Server

Central hub for Gatetorio gate controllers to register, users to discover devices, and relay commands between app and Pi units.

## Architecture Overview

- **MQTT Broker**: Mosquitto for real-time device communication
- **REST API**: FastAPI for registration/discovery/management
- **Database**: SQLite (development) → PostgreSQL (production)
- **Identity System**: Dual identity with immutable hardware_id + mutable controller_id

## Components

### 1. MQTT Broker (Mosquitto)
- **Topics**:
  - `gatetorio/{controller_id}/commands` - Commands from app to Pi
  - `gatetorio/{controller_id}/status` - Status updates from Pi to app
- **Authentication**: Username/password (ACLs planned)
- **Ports**: 1883 (unencrypted), 8883 (SSL planned)

### 2. FastAPI Service
- Device registration (Pi boots and registers)
- User authorization (BLE token mapping)
- Device discovery (app queries for accessible devices)
- Sharing token generation (engineer handoffs)
- Config/log file management

### 3. Database Schema
- `devices`: hardware_id, controller_id, last_seen, firmware_version
- `user_auth`: device_id, user_token, access_level
- `sharing_tokens`: token, source_device, expiry, used_by

### 4. Admin Web Interface
- Device registry view
- User access management
- System monitoring

## Communication Flows

### Device Registration
1. Pi boots → registers with server (hardware_id + controller_id + firmware_version)
2. Server generates MQTT credentials
3. Pi connects to MQTT broker, subscribes to command topic

### User Authorization
1. User pairs via BLE → Pi captures app/device token
2. Pi sends token to server → maps token to controller_id
3. User can now discover device remotely

### Command Relay
1. App publishes to `gatetorio/{controller_id}/commands`
2. Pi receives and executes
3. Pi publishes status to `gatetorio/{controller_id}/status`
4. App receives status updates

### Data Transfer
- **Small data**: MQTT JSON messages (configs, recent logs)
- **Large files**: HTTP download with temporary URLs via MQTT

## Deployment

**Server**: stoner.team (Ubuntu 24.04)
**Domain**: gates.stoner.team or api.stoner.team
**SSL**: Certbot already configured

## Development Status

Phase 1: Core infrastructure
- [ ] FastAPI project setup
- [ ] SQLite database with models
- [ ] Device registration API
- [ ] MQTT broker integration
- [ ] Basic authentication

Phase 2: Advanced features
- [ ] User authorization system
- [ ] Sharing tokens
- [ ] Admin web interface
- [ ] File management
- [ ] SSL/TLS encryption

## Security Notes

**Current**: Minimal security for development speed
**Planned**: TLS, API tokens, MQTT ACLs, rate limiting
