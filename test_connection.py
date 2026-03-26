import server
try:
    uid = server.get_uid()
    print("UID:", uid)
except Exception as e:
    print("Error:", repr(e))
