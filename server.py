"""
Servidor local – Catálogo Tecnigass
Uso: python server.py
Abre: http://localhost:8080
"""

import xmlrpc.client
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

# ── Odoo credentials (from config.json) ───────────────────────
import os, sys
_config_file = 'config.json'
if not os.path.exists(_config_file):
    print(f"Error: Falta el archivo '{_config_file}'. Crea uno copiando 'config.example.json'.")
    sys.exit(1)

with open(_config_file, 'r', encoding='utf-8') as f:
    _config = json.load(f)

ODOO_URL    = _config.get('ODOO_URL', 'https://tecnigass.pe')
ODOO_DB     = _config.get('ODOO_DB', 'db_tecnigas')
ODOO_USER   = _config.get('ODOO_USER', '')
ODOO_APIKEY = _config.get('ODOO_APIKEY', '')

_uid = None

def get_uid():
    global _uid
    if _uid:
        return _uid
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    _uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_APIKEY, {})
    return _uid

def odoo_call(model, method, args, kwargs):
    uid = get_uid()
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    return models.execute_kw(ODOO_DB, uid, ODOO_APIKEY, model, method, args, kwargs)


# ── HTTP Handler ──────────────────────────────────────────────
class Handler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == '/api':
            params = dict(urllib.parse.parse_qsl(parsed.query))
            action = params.get('action', 'search')
            try:
                if action == 'search':
                    result = self.handle_search(params)
                elif action == 'categories':
                    result = self.handle_categories()
                elif action == 'products_by_ids':
                    result = self.handle_products_by_ids(params)
                else:
                    result = {'error': 'Acción no reconocida'}
            except Exception as e:
                result = {'error': str(e)}

            body = json.dumps(result, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        super().do_GET()

    # ── Search products (lightweight, for picker) ──
    def handle_search(self, params):
        q     = params.get('q', '').strip()
        categ = int(params.get('categ', 0) or 0)

        domain: list = [['active', '=', True], ['sale_ok', '=', True]]
        if q:
            domain += ['|', ['name', 'ilike', q], ['default_code', 'ilike', q]]
        if categ:
            domain.append(['categ_id', 'child_of', categ])

        products = odoo_call('product.template', 'search_read', [domain], {
            'fields': ['name', 'default_code', 'barcode', 'categ_id',
                       'list_price', 'qty_available', 'uom_id', 'image_128'],
            'limit': 120,
            'order': 'default_code asc',
        })
        return {'products': products or []}

    # ── Categories ──
    def handle_categories(self):
        cats = odoo_call('product.category', 'search_read', [[]], {
            'fields': ['id', 'name', 'complete_name'],
            'order': 'complete_name asc',
        })
        return {'categories': cats or []}

    # ── Full product data by IDs (high-res image, for catalog) ──
    def handle_products_by_ids(self, params):
        raw_ids = params.get('ids', '')
        try:
            ids = [int(i) for i in raw_ids.split(',') if i.strip()]
        except ValueError:
            return {'error': 'IDs inválidos'}

        if not ids:
            return {'products': []}

        products = odoo_call('product.template', 'search_read',
            [[['id', 'in', ids]]],
            {
                'fields': ['id', 'name', 'default_code', 'barcode',
                           'list_price', 'categ_id', 'uom_id',
                           'image_1920'],   # alta resolución
                'order': 'categ_id asc, default_code asc',
            })
        return {'products': products or []}

    def log_message(self, fmt, *args):   # limpia output en consola
        print(f'  [{self.address_string()}] {fmt % args}')


# ── Main ──────────────────────────────────────────────────────
if __name__ == '__main__':
    port = 8080
    print(f'\n🔥 Catálogo Tecnigass corriendo en http://localhost:{port}')
    print('   Presiona Ctrl+C para detener\n')
    HTTPServer(('', port), Handler).serve_forever()
