module.exports = {
  apps: [
    {
      name: 'ryumem-server',
      cwd: './',
      script: '.venv/bin/python',
      args: '-m uvicorn main:app --host 0.0.0.0 --port 8001',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
      },
      error_file: './logs/error.log',
      out_file: './logs/out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10,
      kill_timeout: 3000,
    },
  ],
};
