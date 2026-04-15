import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8000/api/', data=json.dumps({'model': 'payment', 'action': 'list'}).encode(), headers={'Content-Type': 'application/json'})
try:
    res = urllib.request.urlopen(req)
    print("PAYMENTS:", res.read().decode())
    
    req2 = urllib.request.Request('http://127.0.0.1:8000/api/', data=json.dumps({'model': 'invoice', 'action': 'list'}).encode(), headers={'Content-Type': 'application/json'})
    res2 = urllib.request.urlopen(req2)
    print("INVOICES:", res2.read().decode())
except Exception as e:
    print(e.read().decode())
