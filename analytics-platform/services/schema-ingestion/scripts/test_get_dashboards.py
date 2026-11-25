import urllib.request, json

login_data = "username=admin%40example.com&password=ChangeMe%21SecurePassword123"
login_req = urllib.request.Request(
    "http://127.0.0.1:8000/auth/login",
    data=login_data.encode("utf-8"),
    headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(login_req) as res:
    token = json.loads(res.read().decode("utf-8"))["access_token"]

req = urllib.request.Request(
    "http://127.0.0.1:8000/dashboards",
    headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"}
)
try:
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode("utf-8"))
        print(f"GET /dashboards returned {len(data)} dashboards:")
        for d in data:
            print(f"  - {d['name']} (id={d['id']}, visibility={d['visibility']}, widgets={len(d.get('widgets', []))})")
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode("utf-8"))
