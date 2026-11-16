<?php
declare(strict_types=1);

// Nginx authenticates this endpoint and forwards it to PHP-FPM.
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
$dir = getenv('WATER2_SAVE_DIR') ?: '/var/lib/water2/saves';
$file = "$dir/KOUKAI2.DAT";
$method = $_SERVER['REQUEST_METHOD'];
if ($method !== 'GET' && $method !== 'PUT') {
    header('Allow: GET, PUT');
    http_response_code(405);
    exit;
}
if ($method === 'PUT') {
    if (($_SERVER['CONTENT_TYPE'] ?? '') !== 'application/octet-stream') {
        http_response_code(415);
        exit;
    }
    $body = file_get_contents('php://input', false, null, 0, 333552);
    if ($body === false || strlen($body) !== 333551) {
        http_response_code(422);
        exit;
    }
}
$lock = fopen("$dir/save.lock", 'c');
if (!$lock || !flock($lock, $method === 'GET' ? LOCK_SH : LOCK_EX)) {
    http_response_code(503);
    exit;
}
$exists = is_file($file);
$etag = $exists ? '"' . hash_file('sha256', $file) . '"' : null;
if ($method === 'GET') {
    if (!$exists) {
        http_response_code(204);
        exit;
    }
    header("ETag: $etag");
    header('Content-Type: application/octet-stream');
    readfile($file);
    exit;
}
$next = '"' . hash('sha256', $body) . '"';
if ($next !== $etag) {
    $matches = $exists ? ($_SERVER['HTTP_IF_MATCH'] ?? '') === $etag
                       : ($_SERVER['HTTP_IF_NONE_MATCH'] ?? '') === '*';
    if (!$matches) {
        http_response_code(412);
        exit;
    }
    $tmp = tempnam($dir, '.pending-');
    if ($tmp === false || file_put_contents($tmp, $body) !== strlen($body) || !rename($tmp, $file)) {
        if ($tmp !== false && is_file($tmp)) unlink($tmp);
        http_response_code(500);
        exit;
    }
}
header("ETag: $next");
http_response_code(204);
