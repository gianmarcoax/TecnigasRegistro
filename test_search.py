import server
try:
    print("Testing get_uid():", server.get_uid())
    res = server.odoo_call('product.template', 'search_read', [[['active', '=', True]]], {'limit': 1})
    print("Testing odoo_call product.template search_read:", len(res))
except Exception as e:
    print("Error:", repr(e))
