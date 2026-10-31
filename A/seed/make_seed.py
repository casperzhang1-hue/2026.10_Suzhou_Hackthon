# -*- coding: utf-8 -*-
"""
生成 30 天（实为 45 天）seed 数据 —— 给 B 灌库用。

为什么是 45 天不是 30 天：
  任务卡写「造 30 天假数据」，但记忆屏要引用「41 天前说的那句话」。
  30 天覆盖不到 41 天前 → 记忆屏会自相矛盾（评委最爱抓这个）。
  所以拉到 45 天，保证 D22 的承诺真实存在、且能算出 48%。

故事线（任务卡 D 部分）：
  D1-D7   正常学，仓鼠从休眠长到踏实
  D8      断签（加班）→ 只掉 25%（非对称证据）
  D9      回来 → 立刻回暖
  D15     崩了一次，凌晨 2 点还在学 → 疲惫，说「今天别学了」
  D16-D21 恢复
  D22     说了「资料分析我一定能拿下」← 记忆屏引用这条
  D23-D29 资料分析正确率反而下滑
  D30     今天（留空，等现场 demo 上传）
"""
import json, os, datetime

TODAY = datetime.date(2026, 10, 31)
MODULES = ['资料分析', '言语理解', '判断推理', '数量关系', '常识判断']


def day(days_ago, minutes, start, end, mods, note=''):
    """mods: [(模块名, 题量, 正确数), ...]"""
    q = sum(m[1] for m in mods)
    c = sum(m[2] for m in mods if m[2] is not None)
    return {
        'date': (TODAY - datetime.timedelta(days=days_ago)).isoformat(),
        'days_ago': days_ago,
        'start_time': start,
        'end_time': end,
        'duration_minutes': minutes,
        'source_app': '粉笔',
        'modules': [{'name': m[0], 'question_count': m[1], 'correct_count': m[2]} for m in mods],
        'total_questions': q,
        'accuracy': round(c / q, 2) if q else None,
        'note': note,
    }


days = []

# ---- 第 1 周（days_ago 44~38）：起步，仓鼠从休眠长出来 ----
days.append(day(44, 35, '21:10', '21:45', [('言语理解', 15, 9), ('资料分析', 10, 6)], '刚开始，学得短'))
days.append(day(43, 48, '21:00', '21:48', [('资料分析', 20, 14), ('判断推理', 10, 6)], ''))
days.append(day(42, 62, '20:40', '21:42', [('资料分析', 25, 18), ('言语理解', 15, 10)], ''))
# ↓ 41 天前：承诺那条，记忆屏要引用
days.append(day(41, 70, '20:30', '21:40', [('资料分析', 30, 22), ('判断推理', 10, 7)], '说了「资料分析我一定能拿下」'))
days.append(day(40, 55, '21:20', '22:15', [('资料分析', 25, 17), ('数量关系', 10, 5)], ''))
days.append(day(39, 75, '20:20', '21:35', [('资料分析', 30, 23), ('常识判断', 15, 9)], ''))
days.append(day(38, 68, '20:50', '21:58', [('言语理解', 20, 15), ('资料分析', 20, 14)], ''))

# ---- days_ago 37：D8 断签（加班）----
days.append(day(37, 0, None, None, [], '加班，断签一天 → 仓鼠只掉 25%（非对称证据）'))

# ---- days_ago 36：D9 回来，立刻回暖 ----
days.append(day(36, 58, '21:00', '21:58', [('资料分析', 25, 18), ('言语理解', 10, 7)], '回来第一天，活力立刻回暖'))

# ---- 第 2-3 周（35~31）：稳步上升 ----
days.append(day(35, 80, '20:30', '21:50', [('资料分析', 30, 24), ('判断推理', 15, 11)], ''))
days.append(day(34, 65, '21:10', '22:15', [('言语理解', 25, 19), ('资料分析', 15, 11)], ''))
days.append(day(33, 90, '20:10', '21:40', [('资料分析', 35, 27), ('数量关系', 15, 9)], ''))
days.append(day(32, 72, '20:50', '22:02', [('判断推理', 25, 18), ('资料分析', 20, 15)], ''))
days.append(day(31, 85, '20:00', '21:25', [('资料分析', 30, 25), ('常识判断', 20, 14)], ''))

# ---- days_ago 30：D15 崩了一次，凌晨 2 点还在学 → 疲惫态 ----
days.append(day(30, 210, '22:40', '02:10', [('资料分析', 60, 33), ('数量关系', 40, 18)], '熬夜到凌晨 2 点 → 仓鼠「疲惫」，说今天别学了'))

# ---- days_ago 29~23：恢复期（D16-D21）----
days.append(day(29, 30, '21:30', '22:00', [('常识判断', 15, 10)], '崩完第二天，只学了半小时'))
days.append(day(28, 45, '21:00', '21:45', [('言语理解', 20, 14)], ''))
days.append(day(27, 60, '20:50', '21:50', [('资料分析', 25, 17), ('判断推理', 10, 6)], ''))
days.append(day(26, 70, '20:40', '21:50', [('资料分析', 30, 21), ('言语理解', 15, 11)], ''))
days.append(day(25, 78, '20:30', '21:48', [('资料分析', 30, 23), ('判断推理', 15, 10)], ''))
days.append(day(24, 66, '21:00', '22:06', [('资料分析', 25, 18), ('常识判断', 15, 10)], ''))
days.append(day(23, 74, '20:40', '21:54', [('资料分析', 30, 21), ('数量关系', 15, 8)], '资料分析开始下滑'))

# ---- days_ago 22~8：资料分析持续下滑 ----
days.append(day(22, 68, '20:50', '21:58', [('资料分析', 30, 19), ('言语理解', 15, 11)], ''))
days.append(day(21, 72, '20:40', '21:52', [('资料分析', 30, 18), ('判断推理', 15, 10)], ''))
days.append(day(20, 60, '21:10', '22:10', [('资料分析', 25, 15), ('常识判断', 15, 10)], ''))
days.append(day(19, 0, None, None, [], '又断了一天'))
days.append(day(18, 55, '21:00', '21:55', [('资料分析', 25, 14), ('言语理解', 15, 11)], '回来了，但资料分析明显掉了'))
days.append(day(17, 64, '20:50', '21:54', [('资料分析', 25, 13), ('判断推理', 15, 11)], ''))
days.append(day(16, 58, '21:00', '21:58', [('资料分析', 25, 13), ('数量关系', 10, 6)], ''))
days.append(day(15, 70, '20:40', '21:50', [('资料分析', 30, 15), ('言语理解', 15, 12)], ''))
days.append(day(14, 62, '20:50', '21:52', [('资料分析', 25, 13), ('常识判断', 15, 11)], ''))
days.append(day(13, 66, '20:40', '21:46', [('资料分析', 25, 12), ('判断推理', 15, 11)], ''))
days.append(day(12, 54, '21:10', '22:04', [('资料分析', 25, 13), ('言语理解', 15, 11)], ''))
days.append(day(11, 60, '21:00', '22:00', [('资料分析', 25, 12), ('数量关系', 10, 6)], ''))
days.append(day(10, 58, '21:00', '21:58', [('资料分析', 25, 12), ('常识判断', 15, 11)], ''))
days.append(day(9, 64, '20:50', '21:54', [('资料分析', 25, 12), ('言语理解', 15, 12)], ''))
days.append(day(8, 56, '21:00', '21:56', [('资料分析', 25, 12), ('判断推理', 15, 11)], ''))

# ---- 本周（days_ago 7~1）：只学 3 天，欠 2 次（缺口行要显示「本周欠 2 次」）----
# 关键：任务卡写「本周 48%」，同时今日屏必须有缺口行（RK-08 唯一防法）。
# 如果本周 7 天全有记录 → owed=0 → 缺口行消失 → RK-08 失守。
# 所以本周只排 3 天学习（在职考生这周忙），3/5 → 欠 2 次，同时资料分析仍是 48%。
# 12*3 = 36 正确 / 25*3 = 75 题 → 36/75 = 48.0%
for ago in (1, 3, 5):
    days.append(day(ago, 62, '20:50', '21:52', [('资料分析', 25, 12), ('言语理解', 15, 11)], '本周'))
for ago in (2, 4, 6, 7):
    days.append(day(ago, 0, None, None, [], '本周没学'))

days.sort(key=lambda d: -d['days_ago'])

# ---- 自洽校验 ----
this_week = [d for d in days if 1 <= d['days_ago'] <= 7 and (d['duration_minutes'] or 0) > 0]
zq = sum(m['question_count'] for d in this_week for m in d['modules'] if m['name'] == '资料分析')
zc = sum(m['correct_count'] for d in this_week for m in d['modules'] if m['name'] == '资料分析')
promise = next(d for d in days if d['days_ago'] == 41)
pz = next(m for m in promise['modules'] if m['name'] == '资料分析')

print('本周资料分析: %d/%d = %.1f%%' % (zc, zq, zc / zq * 100))
print('41 天前（%s）资料分析: %d/%d = %.1f%%' % (promise['date'], pz['correct_count'], pz['question_count'],
                                            pz['correct_count'] / pz['question_count'] * 100))
assert zc / zq == 0.48, '本周必须正好 48%'
assert promise['days_ago'] == 41, '承诺日必须 41 天前'

seed = {
    'user': {
        'id': 'demo_zhang',
        'name': '小张',
        'profile': '在职，考公，目标行测 70+',
        'created_at': (TODAY - datetime.timedelta(days=44)).isoformat(),
    },
    'days': days,
    'memories': [
        {
            'id': 'm1',
            'type': 'promise',
            'days_ago': 41,
            'said_at': promise['date'],
            'quote': '资料分析我一定能拿下',
            'module': '资料分析',
            'then_accuracy': round(pz['correct_count'] / pz['question_count'], 2),
            'week_accuracy': 0.48,
            'question': '你当时少算了什么？',
        },
        {
            'id': 'm2',
            'type': 'event',
            'days_ago': 30,
            'said_at': (TODAY - datetime.timedelta(days=30)).isoformat(),
            'quote': '那天你学到凌晨两点',
            'detail': '210 分钟，60 题对 33 题。仓鼠那天是「疲惫」。',
        },
        {
            'id': 'm3',
            'type': 'event',
            'days_ago': 37,
            'said_at': (TODAY - datetime.timedelta(days=37)).isoformat(),
            'quote': '断了一天，第二天就回来了',
            'detail': '断签只掉 25%，回来立刻回暖 40%。',
        },
    ],
    'gap': {'week_target': 5, 'period': 'week'},
}

here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, 'seed.json')
json.dump(seed, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
mc = os.path.join(os.path.dirname(here), 'mock-server', 'data', 'seed.json')
os.makedirs(os.path.dirname(mc), exist_ok=True)
json.dump(seed, open(mc, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已生成:', out)
print('已同步:', mc)
print('天数:', len(days), '| 有学习记录的天:', len([d for d in days if d['duration_minutes'] > 0]))
