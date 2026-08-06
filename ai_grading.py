"""
作业系统 GPT 辅助判题。

用途：
- 填空/选择：学生答案数学上正确但写法与标准答案不同时，避免误判为错
- 解答/证明题：结合标准答案 + 试题图/解析图判定

启用：环境变量 OPENAI_API_KEY；AI_GRADING_ENABLED 默认开启（设为 false 可关闭）
可选：OPENAI_MODEL（默认 gpt-4o-mini）、AI_GRADING_TIMEOUT（秒，默认 45）
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

_TYPE_LABELS = {
    'choice': '选择题',
    'fill': '填空题',
    'proof': '解答/证明题',
}


def ai_grading_available() -> bool:
    enabled = os.environ.get('AI_GRADING_ENABLED', 'true').lower() not in ('0', 'false', 'no')
    return enabled and bool((os.environ.get('OPENAI_API_KEY') or '').strip())


def _model_name() -> str:
    return (os.environ.get('OPENAI_MODEL') or 'gpt-4o-mini').strip()


def _timeout_sec() -> float:
    try:
        return float(os.environ.get('AI_GRADING_TIMEOUT', '45'))
    except ValueError:
        return 45.0


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ.get('OPENAI_API_KEY'), timeout=_timeout_sec())


def _system_prompt() -> str:
    return (
        '你是严谨的数学作业阅卷助手。根据题干（或试题图）、标准答案与解析（或解析图），'
        '判断学生作答是否数学上正确。\n'
        '规则：\n'
        '1. 只关心数学等价性，忽略空格、大小写、多余标点、LaTeX/纯文本写法差异'
        '（如 1/2 与 \\frac{1}{2}、sqrt(2) 与 √2、47 与 47.0）。\n'
        '2. 选择题：学生写选项字母，或写出与正确选项等价的内容，都可算对；'
        '选了错误选项则算错。\n'
        '3. 填空题：最终数值/表达式等价即算对。\n'
        '4. 解答/证明题：对照解析看结论与关键步骤是否实质正确；表述可不同，'
        '关键推理或最终结论错误则判错。\n'
        '5. 空答、乱写、或与正确结果明显不符 → 错误。拿不准时倾向判错。\n'
        '若附带试题图/解析图，请阅读图片中的数学内容再判断。\n'
        '只返回 JSON：{"correct": true/false, "confidence": 0到1, "reason": "一句中文理由"}'
    )


def _http_image_urls(urls: Optional[Sequence[str]]) -> List[str]:
    out = []
    for u in urls or []:
        s = (u or '').strip()
        if s.startswith('http://') or s.startswith('https://'):
            out.append(s)
    return out[:4]  # 控制成本与上下文


def _text_block(
    *,
    student_answer: str,
    correct_answer: str,
    solution: str,
    stem: str,
    question_type: str,
    has_images: bool,
) -> str:
    qtype = (question_type or 'fill').strip().lower()
    label = _TYPE_LABELS.get(qtype, qtype)
    parts = [f'题型：{label}']
    if stem.strip():
        parts.append(f'题干文字：\n{stem.strip()[:2500]}')
    elif has_images:
        parts.append('题干：见附图（试题图）。')
    if correct_answer.strip():
        parts.append(f'标准答案：{correct_answer.strip()[:500]}')
    if solution.strip():
        parts.append(f'解析文字：\n{solution.strip()[:3500]}')
    elif has_images:
        parts.append('解析：若有解析附图请对照阅读。')
    parts.append(f'学生答案：{student_answer.strip()[:2000] if student_answer.strip() else "（空）"}')
    parts.append('请判断学生是否答对，只返回 JSON。')
    return '\n'.join(parts)


def _parse_bool_result(raw: str) -> Optional[bool]:
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{\s*"correct"\s*:\s*(true|false)', text, re.I)
        if not m:
            return None
        return m.group(1).lower() == 'true'
    if isinstance(data, dict) and 'correct' in data:
        return bool(data['correct'])
    return None


def grade_with_ai(
    *,
    student_answer: str,
    correct_answer: str = '',
    solution: str = '',
    stem: str = '',
    question_type: str = 'fill',
    image_urls: Optional[Sequence[str]] = None,
) -> Optional[bool]:
    """
    单题 AI 判分。成功返回 True/False；未启用或失败返回 None（调用方回退规则判分）。
    image_urls：试题图、解析图的 http(s) 地址（如 Cloudinary），可选。
    """
    if not ai_grading_available():
        return None
    student_answer = (student_answer or '').strip()
    if not student_answer or student_answer.upper() == 'IDK':
        return False

    imgs = _http_image_urls(image_urls)
    if not (correct_answer or '').strip() and not (solution or '').strip() and not imgs:
        return None

    text = _text_block(
        student_answer=student_answer,
        correct_answer=correct_answer or '',
        solution=solution or '',
        stem=stem or '',
        question_type=question_type or 'fill',
        has_images=bool(imgs),
    )

    if imgs:
        user_content: Any = [{'type': 'text', 'text': text}]
        for url in imgs:
            user_content.append({'type': 'image_url', 'image_url': {'url': url}})
    else:
        user_content = text

    try:
        client = _client()
        resp = client.chat.completions.create(
            model=_model_name(),
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': _system_prompt()},
                {'role': 'user', 'content': user_content},
            ],
        )
        content = (resp.choices[0].message.content or '') if resp.choices else ''
        result = _parse_bool_result(content)
        if result is None:
            logger.warning('AI grading could not parse response: %s', content[:300])
        return result
    except Exception as e:
        logger.warning('AI grading failed: %s', e)
        return None


def maybe_upgrade_with_ai(
    rule_correct: Optional[bool],
    *,
    student_answer: str,
    correct_answer: str = '',
    solution: str = '',
    stem: str = '',
    question_type: str = 'fill',
    image_urls: Optional[Sequence[str]] = None,
    force: bool = False,
) -> Optional[bool]:
    """
    规则判分后再决定是否调用 AI。
    - 规则已判对且非 force：直接 True（省费用）
    - 规则判错 / 未知，或 force=True（解答题）：尝试 AI
    - AI 不可用或失败：返回原 rule_correct
    """
    if rule_correct is True and not force:
        return True
    ai = grade_with_ai(
        student_answer=student_answer,
        correct_answer=correct_answer,
        solution=solution,
        stem=stem,
        question_type=question_type,
        image_urls=image_urls,
    )
    if ai is None:
        return rule_correct
    return ai
