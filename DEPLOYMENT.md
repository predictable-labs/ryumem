# Ryumem Production Deployment with PM2

This guide covers deploying the Ryumem server and dashboard to production using PM2 process manager.

## Prerequisites

- Node.js and npm installed
- Python 3.8+ installed
- PM2 installed globally: `npm install -g pm2`

## Server Deployment

### 1. Setup Server Environment

```bash
cd server

# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your production values:
# - RYUMEM_DB_FOLDER: Path to database folder
# - ADMIN_API_KEY: Secure random string for admin access
```

**Note**: The PM2 configuration is set to use `.venv/bin/python`, so the virtual environment must exist in the server folder.

### 2. Create Logs Directory

```bash
mkdir -p logs
```

### 3. Start Server with PM2

```bash
# Start the server
pm2 start ecosystem.config.js

# Save PM2 process list
pm2 save

# Setup PM2 to start on system boot
pm2 startup
```

### 4. Monitor Server

```bash
# View server status
pm2 status

# View logs
pm2 logs ryumem-server

# Monitor resources
pm2 monit
```

## Dashboard Deployment

### 1. Setup Dashboard Environment

```bash
cd dashboard

# Install dependencies
npm install

# Build the Next.js application
npm run build

# Create environment file (optional, or use env variables)
cp env.template .env.local
# Edit .env.local with:
# - NEXT_PUBLIC_API_URL: URL of your Ryumem server
```

### 2. Create Logs Directory

```bash
mkdir -p logs
```

### 3. Start Dashboard with PM2

```bash
# Start the dashboard
pm2 start ecosystem.config.js

# Save PM2 process list
pm2 save

# Setup PM2 to start on system boot (if not done already)
pm2 startup
```

### 4. Monitor Dashboard

```bash
# View dashboard status
pm2 status

# View logs
pm2 logs ryumem-dashboard

# Monitor resources
pm2 monit
```

## PM2 Management Commands

### Process Control

```bash
# Start all processes
pm2 start all

# Stop specific process
pm2 stop ryumem-server
pm2 stop ryumem-dashboard

# Restart specific process
pm2 restart ryumem-server
pm2 restart ryumem-dashboard

# Delete process from PM2
pm2 delete ryumem-server
pm2 delete ryumem-dashboard

# Reload (zero-downtime restart)
pm2 reload ryumem-dashboard
```

### Monitoring

```bash
# View all process status
pm2 status

# View real-time logs
pm2 logs

# View logs for specific process
pm2 logs ryumem-server
pm2 logs ryumem-dashboard

# Clear logs
pm2 flush

# Monitor CPU/Memory
pm2 monit
```

### Environment Variables

You can override environment variables when starting PM2:

```bash
# Server
cd server
PORT=8080 pm2 start ecosystem.config.js

# Dashboard
cd dashboard
PORT=3001 NEXT_PUBLIC_API_URL=http://your-server:8080 pm2 start ecosystem.config.js
```

## Production Configuration

### Server Configuration (server/ecosystem.config.js)

- **Python**: Uses `.venv/bin/python` from virtual environment
- **Port**: Default 8000 (configurable via --port in args)
- **Memory**: Auto-restart if exceeds 1GB
- **Instances**: 1 (FastAPI handles async)
- **Logs**: `server/logs/error.log` and `server/logs/out.log`

### Dashboard Configuration (dashboard/ecosystem.config.js)

- **Port**: Default 3000 (set via PORT env variable)
- **Memory**: Auto-restart if exceeds 512MB
- **Instances**: 1
- **Logs**: `dashboard/logs/error.log` and `dashboard/logs/out.log`

## Reverse Proxy Setup (Optional)

For production, use nginx as a reverse proxy:

```nginx
# Server API
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# Dashboard
server {
    listen 80;
    server_name dashboard.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## Troubleshooting

### Server Not Starting

1. Ensure virtual environment exists: `cd server && python3.12 -m venv .venv`
2. Check Python dependencies: `source .venv/bin/activate && pip install -r requirements.txt`
3. Verify .env file exists and has correct values
4. Check logs: `pm2 logs ryumem-server`
5. Check port availability: `lsof -i :8000`
6. Verify Python path in ecosystem.config.js points to `.venv/bin/python`

### Dashboard Not Starting

1. Ensure Next.js build completed: `cd dashboard && npm run build`
2. Verify node_modules installed: `npm install`
3. Check logs: `pm2 logs ryumem-dashboard`
4. Check port availability: `lsof -i :3000`

### High Memory Usage

- Adjust `max_memory_restart` in ecosystem.config.js
- Monitor with: `pm2 monit`

### Process Keeps Restarting

- Check logs for errors: `pm2 logs`
- Increase `min_uptime` in ecosystem.config.js if process crashes immediately
- Check `max_restarts` setting

## Security Recommendations

1. **Environment Variables**: Never commit `.env` files
2. **API Keys**: Use strong, random strings for `ADMIN_API_KEY`
3. **Firewall**: Only expose necessary ports (80, 443)
4. **HTTPS**: Use SSL certificates (Let's Encrypt)
5. **User Permissions**: Run PM2 as non-root user
6. **Updates**: Keep dependencies updated regularly

## Backup

Regularly backup:
- Database files: `server/data/*.db`
- Environment configurations: `.env` files
- PM2 process list: `pm2 save`

## Monitoring & Logs

Set up log rotation to prevent disk space issues:

```bash
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```
