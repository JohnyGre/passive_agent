import httpx
from config import GUMROAD_ACCESS_TOKEN

token = GUMROAD_ACCESS_TOKEN
product_id = 'izXE94c4WrpKf749RE_-gQ=='

res = httpx.get(f'https://api.gumroad.com/v2/products/{product_id}', params={'access_token': token})
p = res.json().get('product', {})
print("Product Details:")
print(f"ID: {p.get('id')}")
print(f"Name: {p.get('name')}")
print(f"Short URL: {p.get('short_url')}")
print(f"Files: {p.get('files')}")
print(f"Description: {p.get('description')}")
print(f"Rich Content: {p.get('rich_content')}")
