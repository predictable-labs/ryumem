server {
    server_name app.ryumem.io www.app.ryumem.io;

    # ----- Global Rate Limit -----
    limit_req zone=perip burst=10 nodelay;

    # ----- /api → port 8000 -----
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ----- EVERYTHING ELSE → port 3000 -----
    # "/" → Dashboard App
    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/app.ryumem.io/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/app.ryumem.io/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

}

server {
    if ($host = app.ryumem.io) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    server_name app.ryumem.io www.app.ryumem.io;
    return 404; # managed by Certbot


}