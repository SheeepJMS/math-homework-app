# -*- coding: utf-8 -*-
"""
诊断模块：权限与审计预留（subscription scaffolding）
默认 allow_all 模式，不阻断任何用户。未来启用收费时仅需收紧 has_entitlement 逻辑。
"""
from functools import wraps
import logging
import secrets
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def has_entitlement(user, feature_key):
    """
    统一权限判断入口。
    当前：allow_all 模式，恒返回 True，仅记录日志。
    未来：基于 diag_subscriptions 的 status/plan/entitlements_json 判断。
    """
    from flask import current_app
    allow_all = not current_app.config.get('BILLING_ENABLED', False)
    if allow_all:
        logger.debug('[auth_ext] has_entitlement(user=%s, feature=%s) -> True (allow_all mode, BILLING_ENABLED=false)',
                     getattr(user, 'id', None), feature_key)
        return True
    # 未来：查 subscription，检查 status in (active, trialing), plan, entitlements_json
    # if not user: return False
    # sub = DiagSubscription.query.filter_by(user_id=user.id).order_by(...).first()
    # if not sub or sub.status not in ('active','trialing'): return False
    # ...
    return True


def require_entitlement(feature_key):
    """
    装饰器：要求用户拥有某功能权限。
    当前：默认放行，仅记录日志。未来启用时返回 403。
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from flask import g, redirect, url_for, abort
            user = getattr(g, 'diag_user', None)
            if has_entitlement(user, feature_key):
                return f(*args, **kwargs)
            logger.warning('[auth_ext] require_entitlement(%s) denied for user=%s', feature_key, getattr(user, 'id', None))
            abort(403)
        return wrapped
    return decorator


def generate_reset_token(user, expires_hours=24):
    """
    预留：生成密码重置 token。
    当前不启用 UI，仅占位。
    """
    from app import db
    from app import DiagPasswordResetToken
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    rec = DiagPasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    db.session.add(rec)
    db.session.commit()
    return token


def verify_reset_token(token):
    """
    预留：验证密码重置 token，返回 user 或 None。
    """
    from app import DiagPasswordResetToken
    rec = DiagPasswordResetToken.query.filter_by(token=token).first()
    if not rec or rec.expires_at < datetime.utcnow():
        return None
    return rec.user


def log_auth_audit(user_id, event, ip=None, user_agent=None):
    """预留：记录登录/登出审计。当前不强制调用。"""
    try:
        from app import db
        from app import DiagAuthAudit
        rec = DiagAuthAudit(user_id=user_id, event=event, ip=ip, user_agent=user_agent)
        db.session.add(rec)
        db.session.commit()
    except Exception as e:
        logger.warning('[auth_ext] log_auth_audit failed: %s', e)


def check_concurrent_sessions(user, max_sessions=5):
    """
    预留：同时在线数量限制。当前不启用，恒返回 True。
    """
    return True
