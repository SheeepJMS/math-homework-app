# 诊断模块订阅收费预留架构（Scaffolding）

本文档记录本次预留型架构改造的交付清单与未来启用说明。**所有改动仅限诊断模块，不触及作业网站。**

---

## 一、新增/修改文件列表

| 路径 | 用途 |
|------|------|
| `migrations/versions/i0d1e2f3a4b5_diag_subscription_scaffolding.py` | 诊断表迁移：email、reset_tokens、subscriptions、support、audit |
| `diagnostic/auth_ext.py` | 权限与审计占位：has_entitlement、require_entitlement、generate_reset_token、verify_reset_token、log_auth_audit |
| `diagnostic/billing.py` | billing 占位路由：/diagnostic/billing/plans、checkout、portal、webhook |
| `templates/diagnostic/billing_coming_soon.html` | billing 占位页 |
| `templates/diagnostic/legal/terms.html` | 服务条款占位 |
| `templates/diagnostic/legal/privacy.html` | 隐私政策占位 |
| `templates/diagnostic/legal/data_request_placeholder.html` | 数据删除/导出请求占位 |
| `templates/diagnostic/legal/support_placeholder.html` | 帮助入口占位 |
| `app.py` | 新增模型、配置、注册 billing_bp |
| `templates/diagnostic/base.html` | 预留帮助按钮（DIAG_SHOW_HELP_BUTTON 控制） |
| `diagnostic/routes.py` | 新增 legal、support、data-request 路由 |

---

## 二、数据库表/字段清单

| 表/字段 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| **diag_users** | | | |
| email | VARCHAR(255) | NULL | 预留，当前注册不要求 |
| email_verified | BOOLEAN | false | 预留 |
| **diag_password_reset_tokens** | | | 新建表 |
| id, user_id, token, expires_at, created_at | | | 预留，不启用 UI |
| **diag_subscriptions** | | | 新建表 |
| plan | VARCHAR(32) | 'legacy_active' | free/trial/pro/legacy_active |
| status | VARCHAR(32) | 'active' | active/trialing/past_due/canceled/none |
| current_period_end, provider, provider_customer_id, provider_subscription_id, entitlements_json | | | 预留 Stripe |
| **diag_support_tickets** | | | 新建表 |
| user_id, category, message, attachment_url, status | | | 预留客服工单 |
| **diag_auth_audit** | | | 新建表 |
| user_id, event, ip, user_agent, created_at | | | 预留登录审计 |

**为何不影响现有用户**：新字段均为 nullable 或带默认值；has_entitlement 默认放行；不创建订阅记录也视为有权限。

---

## 三、核心占位接口签名

### has_entitlement(user, feature_key) -> bool

```python
# diagnostic/auth_ext.py
def has_entitlement(user, feature_key):
    """当前：BILLING_ENABLED=false 时恒返回 True。未来：查 diag_subscriptions 判断。"""
```

### require_entitlement(feature_key)

```python
# diagnostic/auth_ext.py
def require_entitlement(feature_key):
    """装饰器。当前：放行。未来：无权限时 abort(403)。"""
```

### billing_webhook_handler(event)

```python
# diagnostic/billing.py
def billing_webhook_handler(event):
    """占位：未来根据 event.type 更新 diag_subscriptions。当前不调用。"""
```

### generate_reset_token(user, expires_hours=24) -> str

```python
# diagnostic/auth_ext.py
def generate_reset_token(user, expires_hours=24):
    """预留：生成密码重置 token。"""
```

### verify_reset_token(token) -> user or None

```python
# diagnostic/auth_ext.py
def verify_reset_token(token):
    """预留：验证 token，返回 user。"""
```

---

## 四、未来启用收费时的改动点（5 条以内）

1. **has_entitlement**：将 `allow_all` 改为基于 `diag_subscriptions.status`（active/trialing）与 `plan` 判断。
2. **checkout / portal**：实现 Stripe Checkout Session 与 Customer Portal 跳转。
3. **webhook**：启用 `STRIPE_WEBHOOK_SECRET` 验签，在 `billing_webhook_handler` 中根据 `customer.subscription.updated/deleted`、`invoice.payment_failed` 等更新 `diag_subscriptions`。**权限开通/续费失败必须以 webhook 落库为准，不可信前端回调。**
4. **配置**：设置 `BILLING_ENABLED=true`、`STRIPE_WEBHOOK_SECRET`。
5. **帮助入口**：设置 `app.config['DIAG_SHOW_HELP_BUTTON'] = True`。

---

## 五、配置项

| 配置 | 默认 | 说明 |
|------|------|------|
| BILLING_ENABLED | false | 环境变量，未来启用收费时设为 true |
| STRIPE_WEBHOOK_SECRET | '' | 环境变量，webhook 验签用 |
| DIAG_SHOW_HELP_BUTTON | False | 帮助按钮是否显示 |

---

## 六、路由一览（预留，不对外展示入口）

| 路径 | 说明 |
|------|------|
| /diagnostic/billing/plans | 套餐列表占位 |
| /diagnostic/billing/checkout | 结账占位 |
| /diagnostic/billing/portal | 客户门户占位 |
| /diagnostic/billing/webhook | Webhook 占位（仅记录） |
| /diagnostic/legal/terms | 服务条款 |
| /diagnostic/legal/privacy | 隐私政策 |
| /diagnostic/legal/data-request | 数据请求占位 |
| /diagnostic/support | 帮助占位 |
