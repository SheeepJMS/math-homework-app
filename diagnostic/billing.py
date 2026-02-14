# -*- coding: utf-8 -*-
"""
诊断模块：billing 占位路由（subscription scaffolding）
不对外展示入口，默认返回 coming soon。
未来启用 Stripe 时：补实现 checkout/portal，启用 webhook 验签。
强制：权限开通/续费失败必须以 webhook 落库为准，不可信前端回调。
"""
import logging
from flask import Blueprint, render_template, request, jsonify

logger = logging.getLogger(__name__)

billing_bp = Blueprint('diagnostic_billing', __name__, url_prefix='/diagnostic/billing', template_folder='../templates/diagnostic')


def _get_diag_user():
    """从 cookie 获取诊断用户（供 base 模板 nav 使用）。"""
    from diagnostic.routes import get_diag_user_from_cookie
    return get_diag_user_from_cookie()


@billing_bp.route('/plans')
def plans():
    """占位：套餐列表。未来展示 Stripe 产品价格。"""
    return render_template('diagnostic/billing_coming_soon.html', title='套餐', user=_get_diag_user())


@billing_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """占位：结账。未来 Stripe Checkout Session。"""
    return render_template('diagnostic/billing_coming_soon.html', title='结账', user=_get_diag_user())


@billing_bp.route('/portal')
def portal():
    """占位：客户门户。未来 Stripe Customer Portal。"""
    return render_template('diagnostic/billing_coming_soon.html', title='管理订阅', user=_get_diag_user())


@billing_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    占位：Stripe Webhook。
    当前：仅记录收到的事件，不做任何业务变更。
    未来：验签 (STRIPE_WEBHOOK_SECRET)，解析 event，落库 diag_subscriptions。
    强制：权限开通/续费失败必须以 webhook 落库为准，不可信前端回调。
    """
    payload = request.get_data(as_text=True)
    sig = request.headers.get('Stripe-Signature', '')
    # TODO: 启用时 verify signature
    # wh_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    # if wh_secret: stripe.Webhook.construct_event(payload, sig, wh_secret)
    logger.info('[billing] webhook received, sig_len=%s, payload_len=%s', len(sig), len(payload))
    return jsonify({'received': True})


def billing_webhook_handler(event):
    """
    占位：Webhook 事件处理。当前不调用。
    未来：根据 event.type 更新 diag_subscriptions。
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_failed
    等。
    """
    logger.info('[billing] webhook_handler event type=%s', getattr(event, 'type', None))
