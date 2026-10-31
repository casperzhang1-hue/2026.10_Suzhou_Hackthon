# -*- coding: utf-8 -*-
"""把原型同步成前端入口（唯一真相在 原型/ 里）。

用法： python A-module-frontend/sync_frontend.py

会写两份：
  1) A-module-frontend/index.html        ← 双击 / 静态托管 / GitHub Pages 的入口
  2) A-module-frontend/app/public/prototype.html  ← npm run dev 时 app/index.html 跳转到这里

什么时候跑：改完 原型/仓鼠陪跑_原型_接真数据_单文件版.html 之后跑一次。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '原型', '仓鼠陪跑_原型_接真数据_单文件版.html')
DSTS = [
    os.path.join(HERE, 'index.html'),
    os.path.join(HERE, 'app', 'public', 'prototype.html'),
]

MARK = ('<!-- 自动生成，别直接改这个文件。\n'
        '     源文件：A-module-frontend/原型/仓鼠陪跑_原型_接真数据_单文件版.html\n'
        '     改完源文件后跑：python A-module-frontend/sync_frontend.py -->\n')

raw = open(SRC, encoding='utf-8').read()
assert raw.startswith('<!doctype html>'), '源文件开头不是 <!doctype html>，先确认版本'
out = raw.replace('<!doctype html>\n', '<!doctype html>\n' + MARK, 1)

for dst in DSTS:
    if not os.path.isdir(os.path.dirname(dst)):
        print('跳过（目录不存在）->', dst)
        continue
    open(dst, 'w', encoding='utf-8').write(out)
    print('已同步 ->', dst, os.path.getsize(dst), 'B')
