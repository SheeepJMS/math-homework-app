"""
作业系统 AI 导学：结合试题图/解析图，用苏格拉底式提问引导学生理解题目。

启用：OPENAI_API_KEY；可选 AI_TUTOR_ENABLED（默认 true）、OPENAI_MODEL、AI_GRADING_TIMEOUT。
每题对话由前端持有历史；服务端限制学生发言不超过 MAX_STUDENT_TURNS 次。
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

MAX_STUDENT_TURNS = 10
TEACHER_FALLBACK = '该题需要询问老师答疑'

_TYPE_LABELS = {
    'choice': '选择题',
    'fill': '填空题',
    'proof': '解答/证明题',
}


def tutor_available() -> bool:
    enabled = os.environ.get('AI_TUTOR_ENABLED', 'true').lower() not in ('0', 'false', 'no')
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


def _http_image_urls(urls: Optional[Sequence[str]]) -> List[str]:
    out = []
    for u in urls or []:
        s = (u or '').strip()
        if s.startswith('http://') or s.startswith('https://'):
            out.append(s)
    return out[:4]


def _system_prompt() -> str:
    return (
        '你是耐心的中学数学一对一辅导老师，正在带领学生理解一道已做过的作业题。\n'
        '规则：\n'
        '1. 先根据题干（或试题图）与解析（或解析图）真正理解本题思路，再教学。\n'
        '2. 采用苏格拉底式引导：每次只推进一小步，并提出一个具体问题让学生回答；'
        '不要一次性把完整解法讲完。\n'
        '3. 根据学生回答判断其困惑点，用更细的步骤或反例讲解；鼓励但不敷衍。\n'
        '4. 可用解析中的关键步骤，但尽量先让学生自己想；学生明显卡住时可给出该步提示。\n'
        '5. 使用简洁中文，数学可用纯文本或简单 LaTeX。\n'
        '6. 若图片模糊、题意不清、或你无法可靠理解本题，设 can_teach=false，'
        'reply 可简短说明无法继续。\n'
        '7. 若教学已足够收束，或学生表示听懂了，设 done=true 并给一句鼓励小结。\n'
        '8. 只返回 JSON：'
        '{"reply":"对学生说的话","can_teach":true/false,"done":true/false}'
    )


def _context_text(
    *,
    question_type: str,
    stem: str,
    correct_answer: str,
    student_answer: str,
    was_correct: Optional[bool],
    has_images: bool,
    student_turns_used: int,
    is_final_turn: bool,
) -> str:
    label = _TYPE_LABELS.get((question_type or '').lower(), question_type or '题目')
    parts = [
        f'题型：{label}',
        f'标准答案：{(correct_answer or "").strip() or "（未提供）"}',
        f'学生当时作答：{(student_answer or "").strip() or "（空/不会做）"}',
    ]
    if was_correct is True:
        parts.append('判分结果：正确（导学用于加深理解）')
    elif was_correct is False:
        parts.append('判分结果：错误（重点帮学生搞清错因）')
    if (stem or '').strip():
        parts.append(f'题干文字：\n{stem.strip()[:2500]}')
    elif has_images:
        parts.append('题干：见附图（试题图）。解析见附图（若有）。')
    parts.append(
        f'本会话学生已发言 {student_turns_used}/{MAX_STUDENT_TURNS} 次。'
    )
    if is_final_turn:
        parts.append(
            '这是学生本会话最后一次发言机会：请简要收束讲解、点明关键一步，'
            '设 done=true，并鼓励学生有疑问去问老师。'
        )
    return '\n'.join(parts)


def _parse_tutor_json(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 容忍纯文本：当作 reply，仍视为可教
        if len(text) > 5:
            return {'reply': text[:2000], 'can_teach': True, 'done': False}
        return None
    if not isinstance(data, dict):
        return None
    reply = data.get('reply')
    if not isinstance(reply, str) or not reply.strip():
        return None
    can_teach = data.get('can_teach', True)
    if isinstance(can_teach, str):
        can_teach = can_teach.lower() not in ('false', '0', 'no')
    done = data.get('done', False)
    if isinstance(done, str):
        done = done.lower() in ('true', '1', 'yes')
    return {
        'reply': reply.strip()[:4000],
        'can_teach': bool(can_teach),
        'done': bool(done),
    }


def _fail_result(reason: str = '') -> Dict[str, Any]:
    return {
        'ok': False,
        'reply': TEACHER_FALLBACK,
        'can_teach': False,
        'done': True,
        'error': reason or 'tutor_failed',
    }


def _build_user_content(context: str, image_urls: List[str], extra: str = '') -> Any:
    text = context
    if extra:
        text = text + '\n\n' + extra
    if not image_urls:
        return text
    parts: List[Dict[str, Any]] = [{'type': 'text', 'text': text}]
    for url in image_urls:
        parts.append({'type': 'image_url', 'image_url': {'url': url}})
    return parts


def start_tutor(
    *,
    question_type: str = 'fill',
    stem: str = '',
    correct_answer: str = '',
    student_answer: str = '',
    was_correct: Optional[bool] = None,
    image_urls: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """开启导学：返回首条 AI 消息。失败时 can_teach=False。"""
    if not tutor_available():
        return _fail_result('tutor_unavailable')

    imgs = _http_image_urls(image_urls)
    context = _context_text(
        question_type=question_type,
        stem=stem,
        correct_answer=correct_answer,
        student_answer=student_answer,
        was_correct=was_correct,
        has_images=bool(imgs),
        student_turns_used=0,
        is_final_turn=False,
    )
    user_content = _build_user_content(
        context,
        imgs,
        extra='请开始导学：用一两句寒暄确认你理解了题目，然后提出第一个引导问题。只返回 JSON。',
    )
    try:
        client = _client()
        resp = client.chat.completions.create(
            model=_model_name(),
            temperature=0.4,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': _system_prompt()},
                {'role': 'user', 'content': user_content},
            ],
        )
        raw = (resp.choices[0].message.content or '') if resp.choices else ''
        parsed = _parse_tutor_json(raw)
        if not parsed:
            logger.warning('AI tutor start parse failed: %s', raw[:300])
            return _fail_result('parse_failed')
        if not parsed['can_teach']:
            return {
                'ok': False,
                'reply': TEACHER_FALLBACK,
                'can_teach': False,
                'done': True,
            }
        return {
            'ok': True,
            'reply': parsed['reply'],
            'can_teach': True,
            'done': bool(parsed.get('done')),
        }
    except Exception as e:
        logger.warning('AI tutor start failed: %s', e)
        return _fail_result(str(e)[:200])


def continue_tutor(
    *,
    question_type: str = 'fill',
    stem: str = '',
    correct_answer: str = '',
    student_answer: str = '',
    was_correct: Optional[bool] = None,
    image_urls: Optional[Sequence[str]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    student_message: str = '',
    student_turns_used: int = 0,
) -> Dict[str, Any]:
    """
    续聊。student_turns_used 为「本条学生消息计入后」的次数（1..MAX）。
    history 为先前气泡 [{"role":"assistant"|"user","content":"..."}, ...]（不含本条 student_message）。
    """
    if not tutor_available():
        return _fail_result('tutor_unavailable')

    msg = (student_message or '').strip()
    if not msg:
        return _fail_result('empty_message')

    if student_turns_used > MAX_STUDENT_TURNS:
        return {
            'ok': False,
            'reply': '本课导学回合已用完。' + TEACHER_FALLBACK,
            'can_teach': False,
            'done': True,
        }

    imgs = _http_image_urls(image_urls)
    is_final = student_turns_used >= MAX_STUDENT_TURNS
    context = _context_text(
        question_type=question_type,
        stem=stem,
        correct_answer=correct_answer,
        student_answer=student_answer,
        was_correct=was_correct,
        has_images=bool(imgs),
        student_turns_used=student_turns_used,
        is_final_turn=is_final,
    )

    messages: List[Dict[str, Any]] = [
        {'role': 'system', 'content': _system_prompt()},
        {
            'role': 'user',
            'content': _build_user_content(
                context,
                imgs,
                extra='以下为导学对话，请继续引导学生。只返回 JSON。',
            ),
        },
    ]
    for h in history or []:
        role = h.get('role')
        content = (h.get('content') or '').strip()
        if role in ('assistant', 'user') and content:
            messages.append({'role': role, 'content': content[:3000]})
    messages.append({'role': 'user', 'content': msg[:2000]})

    try:
        client = _client()
        resp = client.chat.completions.create(
            model=_model_name(),
            temperature=0.4,
            response_format={'type': 'json_object'},
            messages=messages,
        )
        raw = (resp.choices[0].message.content or '') if resp.choices else ''
        parsed = _parse_tutor_json(raw)
        if not parsed:
            logger.warning('AI tutor chat parse failed: %s', raw[:300])
            return _fail_result('parse_failed')
        if not parsed['can_teach']:
            return {
                'ok': False,
                'reply': TEACHER_FALLBACK,
                'can_teach': False,
                'done': True,
            }
        done = bool(parsed.get('done')) or is_final
        return {
            'ok': True,
            'reply': parsed['reply'],
            'can_teach': True,
            'done': done,
        }
    except Exception as e:
        logger.warning('AI tutor chat failed: %s', e)
        return _fail_result(str(e)[:200])
