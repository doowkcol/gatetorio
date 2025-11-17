# Gatetorio Server Deployment Guide

## Prerequisites

- Ubuntu 24.04 server
- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- Domain: gates.stoner.team or api.stoner.team
- Certbot for SSL certificates

## Quick Start (Docker)

### 1. Clone and Setup
```bash
cd /opt
git clone <repository-url>
cd gatetorio/gatetorio-server
cp .env.example .env
```

### 2. Edit Configuration
Edit `.env` file with your settings:
```bash
nano .env
```

Key settings:
- `SECRET_KEY`: Generate with `openssl rand -hex 32`
- `MQTT_BROKER_PASSWORD`: Set a strong password
- `DATABASE_URL`: Use PostgreSQL for production

### 3. Start Services
```bash
docker-compose up -d
```

### 4. Verify
```bash
# Check services are running
docker-compose ps

# Check logs
docker-compose logs -f

# Test API
curl http://localhost:8000/health
```

## Manual Deployment (Ubuntu Server)

### 1. Install Dependencies
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip mosquitto
```

### 2. Setup Application
```bash
cd /opt/gatetorio/gatetorio-server
./scripts/setup.sh
```

### 3. Configure Mosquitto
```bash
sudo cp mosquitto/config/mosquitto.conf /etc/mosquitto/conf.d/gatetorio.conf
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto
```

### 4. Create Systemd Service
Create `/etc/systemd/system/gatetorio-server.service`:
```ini
[Unit]
Description=Gatetorio Central Server
After=network.target mosquitto.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/gatetorio/gatetorio-server
Environment="PATH=/opt/gatetorio/gatetorio-server/venv/bin"
ExecStart=/opt/gatetorio/gatetorio-server/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gatetorio-server
sudo systemctl start gatetorio-server
```

### 5. Configure Nginx (Reverse Proxy)
Create `/etc/nginx/sites-available/gatetorio`:
```nginx
server {
    listen 80;
    server_name gates.stoner.team;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/gatetorio /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. SSL with Certbot
```bash
sudo certbot --nginx -d gates.stoner.team
```

## Firewall Configuration

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow MQTT
sudo ufw allow 1883/tcp  # Unencrypted
sudo ufw allow 8883/tcp  # SSL (when configured)

# Allow WebSocket MQTT
sudo ufw allow 9001/tcp
```

## Database Migration to PostgreSQL

### 1. Install PostgreSQL
```bash
sudo apt install -y postgresql postgresql-contrib
```

### 2. Create Database and User
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE gatetorio;
CREATE USER gatetorio WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE gatetorio TO gatetorio;
\q
```

### 3. Update .env
```bash
DATABASE_URL=postgresql+asyncpg://gatetorio:your_secure_password@localhost/gatetorio
```

### 4. Restart Service
```bash
sudo systemctl restart gatetorio-server
```

## Monitoring

### Check Service Status
```bash
sudo systemctl status gatetorio-server
sudo systemctl status mosquitto
```

### View Logs
```bash
# Application logs
sudo journalctl -u gatetorio-server -f

# Mosquitto logs
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### Test MQTT
```bash
# Subscribe to all topics
mosquitto_sub -h localhost -t 'gatetorio/#' -v

# Publish test message
mosquitto_pub -h localhost -t 'gatetorio/test/status' -m '{"status": "test"}'
```

## Backup and Maintenance

### Backup Database
```bash
# SQLite
cp /opt/gatetorio/gatetorio-server/gatetorio.db /backup/

# PostgreSQL
pg_dump -U gatetorio gatetorio > /backup/gatetorio-$(date +%Y%m%d).sql
```

### Update Server
```bash
cd /opt/gatetorio/gatetorio-server
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart gatetorio-server
```

## Troubleshooting

### Server Won't Start
```bash
# Check logs
sudo journalctl -u gatetorio-server -n 50

# Check configuration
source venv/bin/activate
python -c "from app.core.config import settings; print(settings)"
```

### MQTT Connection Issues
```bash
# Test broker
mosquitto_pub -h localhost -t test -m "test"

# Check broker status
sudo systemctl status mosquitto

# Check broker logs
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### Database Issues
```bash
# SQLite - check file permissions
ls -l gatetorio.db

# PostgreSQL - check connection
psql -U gatetorio -d gatetorio -h localhost
```

## Security Hardening (Production)

1. **Enable MQTT Authentication**
   ```bash
   sudo mosquitto_passwd -c /etc/mosquitto/passwd gatetorio
   ```

2. **Configure SSL for MQTT**
   - Generate certificates with Certbot
   - Update mosquitto.conf with SSL settings

3. **Rate Limiting**
   - Configure Nginx rate limiting
   - Add API rate limiting middleware

4. **Regular Updates**
   - Keep system packages updated
   - Update Python dependencies regularly
   - Monitor security advisories

5. **Monitoring**
   - Set up log monitoring (e.g., Loki, ELK)
   - Configure alerting for errors
   - Monitor resource usage
