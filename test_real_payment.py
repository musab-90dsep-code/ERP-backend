import urllib.request, json
payload = {
    'model': 'payment', 
    'action': 'create', 
    'data': {
        'invoice': '425362c2-b5f7-40c8-b738-07000fb2ee8f', 
        'contact': '3d9d04ca-8c94-4cef-841a-d564cabe3033', 
        'type': 'out', 
        'amount': 30,
        'method': 'cash',
        'payment_method_details': {},
        'authorized_signature': 'gfgfd',
        'received_by': ''
    }
}
req = urllib.request.Request('http://127.0.0.1:8000/api/', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
try:
    res = urllib.request.urlopen(req)
    print("SUCCESS:", res.read().decode())
except urllib.error.HTTPError as e:
    print("ERROR:", e.read().decode())
