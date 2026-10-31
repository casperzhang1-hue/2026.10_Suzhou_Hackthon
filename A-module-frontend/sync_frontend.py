# -*- coding: utf-8 -*-
"""把原型同步成前端入口 index.html（唯一真相在 原型/ 里）。

用法： python A-module-frontend/sync_frontend.py
什么时候跑：改完 原型/仓鼠陪跑_原型_接真数据_单文件版.html 之后跑一次。
"""
import os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '原型', '仓鼠陪跑_原型_接真数据_单文件版.html')
DST = os.path.join(HERE, 'index.html')

MARK = ('<!-- 自动生成，别直接改这个文件。\n'
        '     源文件：A-module-frontend/原型/仓鼠陪跑_原型_接真数据_单文件版.html\n'
        '     改完源文件后跑：python A-module-frontend/sync_frontend.py -->\n')

raw = open(SRC, encoding='utf-8').read()
assert raw.startswith('<!doctype html>'), '源文件开头不是 <!doctype html>，先确认版本'
open(DST, 'w', encoding='utf-8').write(raw.replace('<!doctype html>\n', '<!doctype html>\n' + MARK, 1))
print('已同步 ->', DST, os.path.getsize(DST), 'B')
