auth_basic "Water2";
auth_basic_user_file /etc/water2/passwords;

location = /api/save {
    client_max_body_size 350k;
    include fastcgi_params;
    fastcgi_param SCRIPT_FILENAME /etc/water2/save.php;
    fastcgi_pass unix:/run/php/php8.4-fpm.sock;
}
