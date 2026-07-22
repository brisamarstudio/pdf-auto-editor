import os
import re

with open('b64.txt', 'r') as f:
    b64 = f.read().strip()

logo_src = f"data:image/png;base64,{b64}"

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

pattern = r'<img src="[^"]*" alt="MyWebby Agency"[^>]*>'
new_img_tag = f'<img src="{logo_src}" alt="MyWebby Agency" style="height: 42px; width: auto; object-fit: contain;" />'

updated_html = re.sub(pattern, new_img_tag, html)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(updated_html)

print("SUCCESS: index.html updated with base64 logo! Total bytes:", len(updated_html))
