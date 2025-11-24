module.exports = {
  apps: [
    {
      name: 'ryumem-dashboard',
      cwd: './',
      script: 'npm',
      args: 'start',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
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
