# 诊断题目：答题页展示类型（选择/填空/证明）与选择题判分
import json
import re


def strip_excel_formula_and_quotes(value):
    """去除 Excel/CSV 常见答案格式（如 =\"13\"）的前导 = 与外层引号。"""
    if value is None:
        return ''
    s = str(value).strip()
    if not s:
        return ''
    if s.startswith('='):
        s = s[1:].strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return s


def normalize_for_compare(raw):
    """判分用归一化：去 Excel 包装后转大写。"""
    return strip_excel_formula_and_quotes(raw).upper()


def parse_mcq_options_from_stem(stem):
    """从题干解析 (A)… (B)… 类格式（Gauss/Waterloo 常见），返回 {'A':'10','B':'12',…} 或 None。"""
    if not stem:
        return None
    s = str(stem)
    pairs = re.findall(
        r'\(\s*([A-Ea-e])\s*\)\s*([^\(]*?)(?=\s*\(\s*[A-Ea-e]\s*\)|\Z)',
        s,
        flags=re.DOTALL,
    )
    if len(pairs) < 2:
        return None
    out = {}
    for letter, text in pairs:
        t = (text or '').strip()
        if t:
            out[letter.upper()] = t
    return out if len(out) >= 2 else None


def diag_question_ui_type(imp, q):
    """答题页应使用的类型：choice | fill | proof。优先 CSV 的 answer_format，否则按答案/选项自动推断。"""
    fmt = (imp.answer_format or '').strip().lower() if imp else ''
    if fmt in ('mcq', 'multiple_choice', 'choice', '选择题'):
        return 'choice'
    if fmt in ('proof', '证明题'):
        return 'proof'
    if fmt in ('fill', 'blank', 'fib', 'numeric', 'text', '填空', '简答'):
        return 'fill'
    # fmt 为空或未知：自动推断
    key = ''
    if imp and (imp.correct_answer or '').strip():
        key = normalize_for_compare(imp.correct_answer)
    elif q and (q.answer_key or '').strip():
        key = normalize_for_compare(q.answer_key)
    if len(key) == 1 and key in 'ABCDE':
        return 'choice'
    if q and q.choices_json:
        try:
            raw = json.loads(q.choices_json)
            if isinstance(raw, dict) and len(raw) >= 2:
                return 'choice'
            if isinstance(raw, list) and len(raw) >= 2:
                return 'choice'
        except Exception:
            pass
    if q and parse_mcq_options_from_stem(q.stem_text):
        return 'choice'
    return 'fill'


def _build_normalized_text_to_letter_map(choices_json=None, stem_text=None):
    """归一化后的选项正文 -> 大写字母 A–E。"""
    d = {}
    if choices_json:
        try:
            raw = json.loads(choices_json)
        except Exception:
            raw = None
        if isinstance(raw, dict):
            for letter, text in raw.items():
                L = normalize_for_compare(str(letter))
                if len(L) == 1 and L in 'ABCDE':
                    T = normalize_for_compare(str(text))
                    if T:
                        d[T] = L
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    k = item.get('key') or item.get('letter')
                    t = item.get('text') or item.get('value') or ''
                    if k is not None:
                        L = normalize_for_compare(str(k))
                        if len(L) == 1 and L in 'ABCDE':
                            T = normalize_for_compare(str(t))
                            if T:
                                d[T] = L
    parsed = parse_mcq_options_from_stem(stem_text) if stem_text else None
    if parsed:
        for letter, text in parsed.items():
            T = normalize_for_compare(str(text))
            if T and T not in d:
                d[T] = letter.upper()
    return d


def mcq_answers_equivalent(student_raw, key_raw, choices_json=None, stem_text=None):
    """
    选择题是否算对：标准答案为字母时，学生可答字母或与某选项正文一致（兼容误用填空提交的数字/文本）。
    无 key 时返回 None（由调用方决定是否给分）。
    """
    key_src = strip_excel_formula_and_quotes(key_raw or '')
    if not key_src:
        return None
    key = normalize_for_compare(key_src)
    ans = normalize_for_compare(student_raw or '')
    if not ans:
        return False
    if key == ans:
        return True
    if len(key) == 1 and key in 'ABCDE':
        m = _build_normalized_text_to_letter_map(choices_json, stem_text)
        letter = m.get(ans)
        if letter and letter == key:
            return True
    return False
