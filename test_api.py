import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8000/api/', data=json.dumps({'model': 'payment', 'action': 'create', 'data': {'invoice': '26e6bf4c-bce8-4eb1-b4c4-7d52f67ac1db', 'contact': 'bd04f326-f404-43cb-b09e-324fbf6cceef', 'type': 'out', 'amount': 30}}).encode(), headers={'Content-Type': 'application/json'})
try:
    res = urllib.request.urlopen(req)
    print(res.read().decode())
except Exception as e:
    print(e.read().decode())
