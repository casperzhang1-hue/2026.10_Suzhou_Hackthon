import base64, os, re

BASE = r'D:/workbuddy1/2026-10-31-08-28-48'
SRC = os.path.join(BASE, 'prototype', '仓鼠陪跑_原型_实拍皮肤版.html')
DST = os.path.join(BASE, 'prototype', '仓鼠陪跑_原型_单文件版.html')
FINAL = os.path.join(BASE, 'hamster-assets', 'final')

html = open(SRC, encoding='utf-8').read()
assert 'img/hamster_01_yuanqi.webp' in html, '先跑 patch_prototype.py'

total_b64 = 0
for name in ['01_yuanqi', '02_tashi', '03_pibei', '04_nianle', '05_xiumian']:
    path = os.path.join(FINAL, f'hamster_{name}_512.webp')
    raw = open(path, 'rb').read()
    b64 = base64.b64encode(raw).decode()
    total_b64 += len(b64)
    html = html.replace(f'img/hamster_{name}.webp', 'data:image/webp;base64,' + b64)
    print(name, len(raw) // 1024, 'KB ->', len(b64) // 1024, 'KB base64')

assert 'img/hamster_' not in html, '仍有未内嵌的图片引用'
open(DST, 'w', encoding='utf-8').write(html)
print('---')
print('单文件体积', os.path.getsize(DST) // 1024, 'KB（内嵌 base64 合计', total_b64 // 1024, 'KB）')
