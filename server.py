"""
Servidor local – Catálogo / Recepción Tecnigass
Uso: python server.py
Abre: http://localhost:8080
"""

import xmlrpc.client
import json
import urllib.parse
import os
import sys
import re
import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler

# ── Odoo credentials (from env vars or config.json) ───────────────
_config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
_config = {}

if os.path.exists(_config_file):
    with open(_config_file, 'r', encoding='utf-8') as f:
        _config = json.load(f)
else:
    print("Aviso: 'config.json' no encontrado. Intentando usar variables de entorno.")

ODOO_URL    = os.environ.get('ODOO_URL') or _config.get('ODOO_URL', 'https://tecnigass.pe')
ODOO_DB     = os.environ.get('ODOO_DB') or _config.get('ODOO_DB', 'db_tecnigas')
ODOO_USER   = os.environ.get('ODOO_USER') or _config.get('ODOO_USER', '')
ODOO_APIKEY = os.environ.get('ODOO_APIKEY') or _config.get('ODOO_APIKEY', '')

if not ODOO_USER or not ODOO_APIKEY:
    print("Error: Faltan credenciales ODOO_USER o ODOO_APIKEY. Revisa config.json o tus variables de entorno.")
    sys.exit(1)

# Carpeta donde se guardan los Excel exportados
EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
TEMPLATE_XLSX = os.path.join(os.path.dirname(os.path.abspath(__file__)), '010.xlsx')

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


# ── Excel rotation helper ─────────────────────────────────────
def rotate_and_save_excel(rows):
    """
    Guarda el Excel con rotación de nombres:
      010.xlsx  →  se renombra a  0100001.xlsx  (o 0100002.xlsx, …)
    El nuevo export siempre queda como  010.xlsx
    Devuelve (ruta_guardada, nombre_archivo)
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    dest_path = os.path.join(EXPORTS_DIR, '010.xlsx')

    # Rotación: si ya existe 010.xlsx, renombrarlo
    if os.path.exists(dest_path):
        # Buscar el siguiente número disponible
        existing = [
            f for f in os.listdir(EXPORTS_DIR)
            if re.match(r'^010\d{4}\.xlsx$', f)
        ]
        nums = []
        for fn in existing:
            m = re.match(r'^010(\d{4})\.xlsx$', fn)
            if m:
                nums.append(int(m.group(1)))
        next_num = max(nums) + 1 if nums else 1
        rotated_name = f'010{next_num:04d}.xlsx'
        rotated_path = os.path.join(EXPORTS_DIR, rotated_name)
        shutil.move(dest_path, rotated_path)

    # Crear nuevo workbook basado en la plantilla si existe
    if os.path.exists(TEMPLATE_XLSX):
        wb = openpyxl.load_workbook(TEMPLATE_XLSX)
        ws = wb.active
        # Limpiar filas de datos (mantener cabecera en fila 1)
        for row_idx in range(ws.max_row, 1, -1):
            ws.delete_rows(row_idx)
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        # Cabecera
        headers = ['Cantidad a la mano', 'Nombre', 'Precio de venta', 'Referencia interna']
        header_fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True)
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')

    # Escribir filas de datos
    thin = Side(style='thin', color='CBD5E1')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row_idx, row in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=row.get('tickets', 1)).border = border
        ws.cell(row=row_idx, column=2, value=row.get('name', '')).border = border
        ws.cell(row=row_idx, column=3, value=row.get('list_price', 0)).border = border
        ws.cell(row=row_idx, column=4, value=row.get('default_code', '')).border = border
        # Ajustar bordes en todas las celdas de la fila
        for col_idx in range(1, 5):
            ws.cell(row=row_idx, column=col_idx).border = border

    # Ajustar ancho de columnas
    col_widths = [20, 45, 18, 20]
    for col_idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

    wb.save(dest_path)
    return dest_path, '010.xlsx'


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
                elif action == 'kit_components':
                    result = self.handle_kit_components(params)
                elif action == 'locations':
                    result = self.handle_locations()
                elif action == 'stock_by_location':
                    result = self.handle_stock_by_location(params)
                else:
                    result = {'error': 'Acción no reconocida'}
            except Exception as e:
                result = {'error': str(e)}

            self._json_response(result)
            return

        # Servir archivos estáticos
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == '/api':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode('utf-8'))
                action = data.get('action', '')
                if action == 'export_excel':
                    result = self.handle_export_excel(data)
                elif action == 'receive':
                    result = self.handle_receive(data)
                elif action == 'transfer':
                    result = self.handle_transfer(data)
                else:
                    result = {'error': 'Acción POST no reconocida'}
            except Exception as e:
                result = {'error': str(e)}

            self._json_response(result)
            return

        self.send_response(405)
        self.end_headers()

    def _json_response(self, result):
        # Añadir cabeceras CORS por si acaso
        body = json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    # ── Search products ──────────────────────────────────────
    def handle_search(self, params):
        q     = params.get('q', '').strip()
        categ = int(params.get('categ', 0) or 0)

        domain = [['active', '=', True], ['sale_ok', '=', True]]
        if q:
            domain += ['|', ['name', 'ilike', q], ['default_code', 'ilike', q]]
        if categ:
            domain.append(['categ_id', 'child_of', categ])

        products = odoo_call('product.template', 'search_read', [domain], {
            'fields': ['id', 'name', 'default_code', 'barcode', 'categ_id',
                       'list_price', 'standard_price', 'qty_available',
                       'uom_id', 'image_128'],
            'limit': 120,
            'order': 'default_code asc',
        })

        # Marcar cuáles son kits (tienen mrp.bom tipo phantom)
        if products:
            tmpl_ids = [p['id'] for p in products]
            try:
                boms = odoo_call('mrp.bom', 'search_read',
                    [[['product_tmpl_id', 'in', tmpl_ids], ['type', '=', 'phantom']]],
                    {'fields': ['product_tmpl_id']})
                kit_ids = {b['product_tmpl_id'][0] for b in boms}
            except Exception:
                kit_ids = set()

            for p in products:
                p['is_kit'] = p['id'] in kit_ids

        return {'products': products or []}

    # ── Categories ────────────────────────────────────────────
    def handle_categories(self):
        cats = odoo_call('product.category', 'search_read', [[]], {
            'fields': ['id', 'name', 'complete_name'],
            'order': 'complete_name asc',
        })
        return {'categories': cats or []}

    # ── Full product data by IDs ───────────────────────────────
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
                           'list_price', 'standard_price', 'categ_id',
                           'uom_id', 'image_1920'],
                'order': 'categ_id asc, default_code asc',
            })
        return {'products': products or []}

    # ── Kit components ────────────────────────────────────────
    def handle_kit_components(self, params):
        """
        Devuelve los componentes de un kit (mrp.bom tipo phantom)
        para un product.template dado.
        """
        tmpl_id = int(params.get('id', 0) or 0)
        if not tmpl_id:
            return {'error': 'Falta el parámetro id'}

        # Buscar la BoM de tipo phantom para este template
        boms = odoo_call('mrp.bom', 'search_read',
            [[['product_tmpl_id', '=', tmpl_id], ['type', '=', 'phantom']]],
            {'fields': ['id', 'product_tmpl_id', 'bom_line_ids'], 'limit': 1})

        if not boms:
            return {'components': [], 'is_kit': False}

        bom = boms[0]
        line_ids = bom.get('bom_line_ids', [])

        if not line_ids:
            return {'components': [], 'is_kit': True}

        # Obtener detalle de cada línea
        lines = odoo_call('mrp.bom.line', 'search_read',
            [[['id', 'in', line_ids]]],
            {'fields': ['product_id', 'product_qty', 'product_uom_id']})

        # Enriquecer con imagen y datos del producto
        product_ids = [l['product_id'][0] for l in lines if l.get('product_id')]
        products_map = {}
        if product_ids:
            prods = odoo_call('product.product', 'search_read',
                [[['id', 'in', product_ids]]],
                {'fields': ['id', 'name', 'default_code', 'list_price',
                            'standard_price', 'image_128']})
            products_map = {p['id']: p for p in prods}

        components = []
        for line in lines:
            if not line.get('product_id'):
                continue
            pid = line['product_id'][0]
            prod = products_map.get(pid, {})
            components.append({
                'product_id': pid,
                'name': prod.get('name', line['product_id'][1]),
                'default_code': prod.get('default_code', ''),
                'list_price': prod.get('list_price', 0),
                'standard_price': prod.get('standard_price', 0),
                'image_128': prod.get('image_128', False),
                'qty_bom': line.get('product_qty', 1),
                'uom': line.get('product_uom_id', [None, ''])[1] if line.get('product_uom_id') else '',
            })

        return {'components': components, 'is_kit': True, 'bom_id': bom['id']}

    # ── Locations ─────────────────────────────────────────────
    def handle_locations(self):
        """
        Devuelve ubicaciones de stock relevantes para la recepción.
        Prioriza PUN/ALMACEN y PUN/TIENDA.
        """
        locs = odoo_call('stock.location', 'search_read',
            [[['usage', '=', 'internal'], ['active', '=', True]]],
            {
                'fields': ['id', 'name', 'complete_name'],
            })

        # Poner primero las ubicaciones de PUNO si existen
        priority = ['ALMACEN', 'TIENDA']
        def sort_key(loc):
            cn = loc.get('complete_name', '').upper()
            for i, kw in enumerate(priority):
                if kw in cn:
                    return (0, i, cn)
            return (1, 0, cn)

        locs_sorted = sorted(locs or [], key=sort_key)
        return {'locations': locs_sorted}

    # ── Export Excel ──────────────────────────────────────────
    def handle_export_excel(self, data):
        """
        Recibe: { action, rows: [{name, default_code, list_price, tickets}, ...] }
        Guarda el Excel con rotación de nombres y devuelve el resultado.
        """
        rows = data.get('rows', [])
        if not rows:
            return {'error': 'No hay productos para exportar'}

        try:
            saved_path, filename = rotate_and_save_excel(rows)
            return {
                'ok': True,
                'filename': filename,
                'path': saved_path,
                'count': len(rows),
            }
        except ImportError:
            return {'error': 'Falta openpyxl. Instala con: pip install openpyxl'}
        except Exception as e:
            return {'error': str(e)}

    def handle_stock_by_location(self, params):
        """
        Devuelve stock (qty_available) de una lista de product.template IDs
        en una ubicación dada.
        GET /api?action=stock_by_location&loc_id=8&tmpl_ids=1,2,3
        """
        loc_id = int(params.get('loc_id', 0) or 0)
        raw_ids = params.get('tmpl_ids', '')
        try:
            tmpl_ids = [int(i) for i in raw_ids.split(',') if i.strip()]
        except ValueError:
            return {'error': 'IDs inválidos'}

        if not loc_id or not tmpl_ids:
            return {'stock': {}}

        # Buscar product.product IDs de esos templates
        prods = odoo_call('product.product', 'search_read',
            [[['product_tmpl_id', 'in', tmpl_ids]]],
            {'fields': ['id', 'product_tmpl_id']})
        prod_to_tmpl = {p['id']: p['product_tmpl_id'][0] for p in prods}
        prod_ids = list(prod_to_tmpl.keys())

        if not prod_ids:
            return {'stock': {}}

        quants = odoo_call('stock.quant', 'search_read',
            [[['location_id', '=', loc_id],
              ['product_id', 'in', prod_ids]]],
            {'fields': ['product_id', 'quantity', 'reserved_quantity']})

        stock = {}  # tmpl_id -> qty disponible
        for q in quants:
            prod_id = q['product_id'][0]
            tmpl_id = prod_to_tmpl.get(prod_id)
            if tmpl_id:
                available = q.get('quantity', 0) - q.get('reserved_quantity', 0)
                stock[tmpl_id] = stock.get(tmpl_id, 0) + available

        return {'stock': stock}

    # ── Receive: crear stock.picking en Odoo ────────────────────
    def handle_receive(self, data):
        """
        Crea un stock.picking de tipo incoming en Odoo y lo valida.
        data: {
          action: 'receive',
          location_dest_id: <int>,   # PUN/ALMACEN o PUN/TIENDA
          rows: [{product_id: int, name: str, qty: float}, ...]
        }
        """
        rows = data.get('rows', [])
        loc_dest_id = int(data.get('location_dest_id', 0) or 0)

        if not rows:
            return {'error': 'No hay productos para recepcionar'}
        if not loc_dest_id:
            return {'error': 'Debes seleccionar un destino (almacén o tienda)'}

        # 1. Encontrar el picking type incoming que tenga ese destino (o el primero incoming del almacén)
        pts = odoo_call('stock.picking.type', 'search_read',
            [[['code', '=', 'incoming'],
              ['default_location_dest_id', '=', loc_dest_id]]],
            {'fields': ['id', 'name', 'default_location_src_id'], 'limit': 1})

        if not pts:
            # Fallback: cualquier picking type incoming
            pts = odoo_call('stock.picking.type', 'search_read',
                [[['code', '=', 'incoming']]],
                {'fields': ['id', 'name', 'default_location_src_id'], 'limit': 1})

        if not pts:
            return {'error': 'No se encontró un tipo de operación de recepción en Odoo'}

        pt = pts[0]
        picking_type_id  = pt['id']
        loc_src_id = pt['default_location_src_id'][0] if pt.get('default_location_src_id') else None

        # Ubicación origen por defecto: proveedor genérico
        if not loc_src_id:
            sup = odoo_call('stock.location', 'search',
                [[['usage', '=', 'supplier']]], {'limit': 1})
            loc_src_id = sup[0] if sup else None

        if not loc_src_id:
            return {'error': 'No se pudo determinar la ubicación de origen (proveedor)'}

        # 2. Crear el picking
        picking_vals = {
            'picking_type_id': picking_type_id,
            'location_id':     loc_src_id,
            'location_dest_id': loc_dest_id,
            'origin': 'Recepción Web',
        }
        picking_id = odoo_call('stock.picking', 'create', [picking_vals], {})

        # 3. Resolver IDs: el frontend envía product.template IDs,
        #    pero stock.move necesita product.product IDs (variante).
        tmpl_ids = list({int(r.get('product_id', 0)) for r in rows if r.get('product_id')})
        tmpl_to_variant = {}
        if tmpl_ids:
            variants = odoo_call('product.product', 'search_read',
                [[['product_tmpl_id', 'in', tmpl_ids], ['active', '=', True]]],
                {'fields': ['id', 'product_tmpl_id', 'uom_id'], 'limit': len(tmpl_ids) * 5})
            for v in variants:
                tid = v['product_tmpl_id'][0]
                if tid not in tmpl_to_variant:
                    tmpl_to_variant[tid] = (v['id'], v['uom_id'][0] if v.get('uom_id') else 1)

        # 4. Crear los movimientos de stock
        for row in rows:
            qty = float(row.get('qty', 1))
            if qty <= 0:
                continue
            tmpl_id = int(row.get('product_id', 0))
            if not tmpl_id:
                continue
            variant_info = tmpl_to_variant.get(tmpl_id)
            if not variant_info:
                print(f'  [RECV] Warning: no variante para template {tmpl_id}')
                continue
            pp_id, uom_id = variant_info
            odoo_call('stock.move', 'create', [{
                'name':             row.get('name', 'Producto'),
                'picking_id':       picking_id,
                'product_id':       pp_id,
                'product_uom_qty':  qty,
                'product_uom':      uom_id,
                'location_id':      loc_src_id,
                'location_dest_id': loc_dest_id,
            }], {})

        # 4. Confirmar y validar la recepción
        odoo_call('stock.picking', 'action_confirm', [[picking_id]], {})
        # Asignar cantidades disponibles
        odoo_call('stock.picking', 'action_assign', [[picking_id]], {})
        # Validar (marcar como Hecho)
        try:
            odoo_call('stock.picking', 'button_validate', [[picking_id]], {})
            state = 'done'
        except Exception as e:
            state = 'confirmed'
            print(f'  [RECV] Validación automática no completada: {e}')

        # Obtener el nombre del picking creado
        pick_data = odoo_call('stock.picking', 'read', [[picking_id]], {'fields': ['name', 'state']})
        pick_name = pick_data[0]['name'] if pick_data else str(picking_id)

        return {
            'ok': True,
            'picking_id': picking_id,
            'picking_name': pick_name,
            'state': state,
            'count': len(rows),
        }

    # ── Transfer: movimiento interno en Odoo ────────────────────
    def handle_transfer(self, data):
        """
        Crea un stock.picking de tipo 'internal' en Odoo (traslado entre ubicaciones).
        data: {
          action: 'transfer',
          location_src_id: <int>,    # PUN/ALMACEN o PUN/TIENDA (origen)
          location_dest_id: <int>,   # PUN/TIENDA o PUN/ALMACEN (destino)
          rows: [{product_id: int, name: str, qty: float}, ...]
        }
        """
        rows         = data.get('rows', [])
        loc_src_id   = int(data.get('location_src_id',  0) or 0)
        loc_dest_id  = int(data.get('location_dest_id', 0) or 0)

        if not rows:        return {'error': 'No hay productos para trasladar'}
        if not loc_src_id:  return {'error': 'Selecciona la ubicación de origen'}
        if not loc_dest_id: return {'error': 'Selecciona la ubicación de destino'}
        if loc_src_id == loc_dest_id:
            return {'error': 'Origen y destino deben ser diferentes'}

        # 1. Buscar picking type internal
        pts = odoo_call('stock.picking.type', 'search_read',
            [[['code', '=', 'internal'],
              ['default_location_src_id', '=', loc_src_id]]],
            {'fields': ['id', 'name'], 'limit': 1})
        if not pts:
            pts = odoo_call('stock.picking.type', 'search_read',
                [[['code', '=', 'internal']]],
                {'fields': ['id', 'name'], 'limit': 1})
        if not pts:
            return {'error': 'No se encontró tipo de operación de traslado interno en Odoo'}

        picking_type_id = pts[0]['id']

        # 2. Crear el picking
        picking_id = odoo_call('stock.picking', 'create', [{
            'picking_type_id':  picking_type_id,
            'location_id':      loc_src_id,
            'location_dest_id': loc_dest_id,
            'origin':           'Traslado Web',
        }], {})

        # 3. Resolver template IDs → product.product IDs
        tmpl_ids = list({int(r.get('product_id', 0)) for r in rows if r.get('product_id')})
        tmpl_to_variant = {}
        if tmpl_ids:
            variants = odoo_call('product.product', 'search_read',
                [[['product_tmpl_id', 'in', tmpl_ids], ['active', '=', True]]],
                {'fields': ['id', 'product_tmpl_id', 'uom_id'], 'limit': len(tmpl_ids) * 5})
            for v in variants:
                tid = v['product_tmpl_id'][0]
                if tid not in tmpl_to_variant:
                    tmpl_to_variant[tid] = (v['id'], v['uom_id'][0] if v.get('uom_id') else 1)

        # 4. Crear movimientos de stock
        for row in rows:
            qty = float(row.get('qty', 1))
            if qty <= 0: continue
            tmpl_id = int(row.get('product_id', 0))
            if not tmpl_id: continue
            variant_info = tmpl_to_variant.get(tmpl_id)
            if not variant_info:
                print(f'  [TRNF] Warning: no variante para template {tmpl_id}')
                continue
            pp_id, uom_id = variant_info
            odoo_call('stock.move', 'create', [{
                'name':             row.get('name', 'Producto'),
                'picking_id':       picking_id,
                'product_id':       pp_id,
                'product_uom_qty':  qty,
                'product_uom':      uom_id,
                'location_id':      loc_src_id,
                'location_dest_id': loc_dest_id,
            }], {})

        # 5. Confirmar, asignar y validar
        odoo_call('stock.picking', 'action_confirm', [[picking_id]], {})
        odoo_call('stock.picking', 'action_assign',  [[picking_id]], {})
        try:
            odoo_call('stock.picking', 'button_validate', [[picking_id]], {})
            state = 'done'
        except Exception as e:
            state = 'confirmed'
            print(f'  [TRNF] Validación parcial: {e}')

        pick_data = odoo_call('stock.picking', 'read', [[picking_id]], {'fields': ['name', 'state']})
        pick_name = pick_data[0]['name'] if pick_data else str(picking_id)

        return {'ok': True, 'picking_id': picking_id, 'picking_name': pick_name,
                'state': state, 'count': len(rows)}

    def log_message(self, fmt, *args):
        print(f'  [{self.address_string()}] {fmt % args}')


# ── Main ──────────────────────────────────────────────────────
if __name__ == '__main__':
    # Siempre servir archivos desde la carpeta del proyecto
    import os
    _base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(_base_dir)
    os.makedirs(os.path.join(_base_dir, 'exports'), exist_ok=True)

    port = int(os.environ.get("PORT", 8080))
    print(f'\n🔥 Tecnigass – Recepción/Catálogo corriendo en puerto {port}')
    print(f'   Dashboard:   http://localhost:{port}/dashboard.html')
    print(f'   Catálogo:    http://localhost:{port}/index.html')
    print(f'   Recepción:   http://localhost:{port}/recepcion.html')
    print(f'   Traslado:    http://localhost:{port}/traslado.html')
    print('   Presiona Ctrl+C para detener\n')
    HTTPServer(('', port), Handler).serve_forever()
