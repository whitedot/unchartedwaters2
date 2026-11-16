#!/bin/sh
# Run as root on saanraan after staging files under ~water2/release.
set -eu
release=/home/water2/release
config=$(readlink -f /etc/nginx/sites-enabled/water2.conf)
install -d -o root -g www-data -m 0750 /etc/water2
install -d -o www-data -g www-data -m 0700 /var/lib/water2/saves
install -o root -g www-data -m 0640 "$release/passwords" /etc/water2/passwords
install -o root -g www-data -m 0640 "$release/save.php" /etc/water2/save.php
install -o root -g root -m 0644 "$release/nginx.inc" /etc/water2/nginx.inc
if ! grep -qF 'include /etc/water2/nginx.inc;' "$config"; then
    cp -p "$config" /etc/water2/nginx-before-auth.conf
    sed -i '/root \/var\/www\/water2;/a\    include /etc/water2/nginx.inc;' "$config"
    if ! nginx -t; then
        cp -p /etc/water2/nginx-before-auth.conf "$config"
        exit 1
    fi
fi
nginx -t
systemctl reload nginx
install -o water2 -g water2 -m 0644 "$release/index.html" /var/www/water2/index.next
mv /var/www/water2/index.next /var/www/water2/index.html
