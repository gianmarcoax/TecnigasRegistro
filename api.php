<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

$configFile = __DIR__ . '/config.json';
if (!file_exists($configFile)) {
    http_response_code(500);
    echo json_encode(['error' => 'Falta el archivo config.json. Crea uno copiando config.example.json.']);
    exit;
}
$config = json_decode(file_get_contents($configFile), true);

define('ODOO_URL', $config['ODOO_URL'] ?? 'https://tecnigass.pe');
define('ODOO_DB', $config['ODOO_DB'] ?? 'db_tecnigas');
define('ODOO_USER', $config['ODOO_USER'] ?? '');
define('ODOO_APIKEY', $config['ODOO_APIKEY'] ?? '');

// ---------- XML-RPC helper ----------
function odoo_call($endpoint, $method, $params)
{
    $url = ODOO_URL . $endpoint;
    $xml = xmlrpc_encode_request($method, $params);

    $ctx = stream_context_create(['http' => [
            'method' => 'POST',
            'header' => "Content-Type: text/xml\r\nContent-Length: " . strlen($xml),
            'content' => $xml,
            'timeout' => 15,
        ]]);

    $raw = @file_get_contents($url, false, $ctx);
    if ($raw === false) {
        return ['error' => 'No se pudo conectar con Odoo'];
    }
    return xmlrpc_decode($raw);
}

// ---------- Auth ----------
function get_uid()
{
    $uid = odoo_call('/xmlrpc/2/common', 'authenticate', [
        ODOO_DB, ODOO_USER, ODOO_APIKEY, []
    ]);
    return (is_int($uid) && $uid > 0) ? $uid : null;
}

$action = $_GET['action'] ?? 'search';
$uid = get_uid();

if (!$uid) {
    echo json_encode(['error' => 'Autenticación fallida']);
    exit;
}

// ---------- Routes ----------
switch ($action) {

    // --- Search products ---
    case 'search':
        $q = trim($_GET['q'] ?? '');
        $categ = intval($_GET['categ'] ?? 0);

        $domain = [['active', '=', true], ['sale_ok', '=', true]];

        if ($q !== '') {
            $domain[] = '|';
            $domain[] = ['name', 'ilike', $q];
            $domain[] = ['default_code', 'ilike', $q];
        }
        if ($categ > 0) {
            $domain[] = ['categ_id', 'child_of', $categ];
        }

        $products = odoo_call('/xmlrpc/2/object', 'execute_kw', [
            ODOO_DB, $uid, ODOO_APIKEY,
            'product.template', 'search_read',
            [$domain],
            [
                'fields' => ['name', 'default_code', 'categ_id', 'list_price',
                    'qty_available', 'uom_id', 'image_128'],
                'limit' => 100,
                'order' => 'default_code asc',
            ]
        ]);

        echo json_encode(['products' => $products ?: []]);
        break;

    // --- List categories ---
    case 'categories':
        $cats = odoo_call('/xmlrpc/2/object', 'execute_kw', [
            ODOO_DB, $uid, ODOO_APIKEY,
            'product.category', 'search_read',
            [[]],
            ['fields' => ['id', 'name', 'complete_name'], 'order' => 'complete_name asc']
        ]);
        echo json_encode(['categories' => $cats ?: []]);
        break;

    default:
        echo json_encode(['error' => 'Acción no reconocida']);
}
