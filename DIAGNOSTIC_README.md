# 诊断模块（Diagnostic）交付说明

## 一、新增目录与文件清单

### 蓝图与逻辑
- `diagnostic/__init__.py` - 诊断包
- `diagnostic/routes.py` - 对外路由 `/diagnostic/*`（注册、登录、试卷列表、答题、报告、练习）
- `diagnostic/admin_routes.py` - 后台路由 `/admin/diagnostic/*`（试卷管理、CSV 导入、题目配置）

### 模板（风格与原 UI 一致：Bootstrap 5）
- `templates/diagnostic/base.html` - 诊断前台基础模板
- `templates/diagnostic/index.html` - 诊断首页
- `templates/diagnostic/register.html` - 注册
- `templates/diagnostic/login.html` - 登录
- `templates/diagnostic/exams.html` - 选择竞赛与试卷
- `templates/diagnostic/start_exam.html` - 开始答题确认
- `templates/diagnostic/attempt.html` - 答题页（题号导航、计时、上一题/下一题/交卷、localStorage 备份）
- `templates/diagnostic/report.html` - 报告页
- `templates/diagnostic/practice.html` - 练习包页
- `templates/admin/diagnostic/exams.html` - 诊断试卷列表（创建/删除/发布）
- `templates/admin/diagnostic/exam_detail.html` - 卷子详情与题目顺序
- `templates/admin/diagnostic/import.html` - CSV 导入页
- `templates/admin/diagnostic/question_config.html` - 单题配置（知识点、练习来源、随机题数、压轴题）

### 数据库
- 所有诊断模型在 `app.py` 中新增（`DiagUser`, `DiagSession`, `DiagCompetition`, `DiagExam`, `DiagQuestion`, `DiagExamQuestion`, `DiagAttempt`, `DiagAttemptAnswer`, `DiagKnowledgePoint`, `DiagQuestionTag`, `DiagBankQuestion`, `DiagBankQuestionTag`, `DiagQuestionBankLink`, `DiagQuestionPracticeConfig`, `DiagPracticeSet`, `DiagPracticeSetItem`）
- `migrations/versions/a1b2c3d4e5f6_add_diagnostic_tables.py` - 仅新增 `diag_*` 表，不 ALTER 任何旧表

### 应用注册（仅新增）
- `app.py` 末尾：注册 `diagnostic_bp`（url_prefix=`/diagnostic`）与 `diagnostic_admin_bp`（url_prefix 已在蓝图中设为 `/admin/diagnostic`）
- `templates/admin/base.html`：新增导航项「诊断管理」链接到 `diagnostic_admin.exams`

---

## 二、迁移与配置

### 运行迁移（仅新增 diag_ 表）
```bash
flask db upgrade
```
或若当前未到 b4fefe386c31：
```bash
flask db stamp b4fefe386c31
flask db upgrade
```

### 可选环境变量（均为 DIAG_ 前缀，不改变原有语义）
- `DIAG_COOKIE_NAME` - 诊断登录 cookie 名，默认 `diag_session`
- `DIAG_SESSION_DAYS` - 诊断会话有效天数，默认 `7`

---

## 三、路由一览

| 路径 | 说明 |
|------|------|
| `/diagnostic` | 诊断首页 |
| `/diagnostic/register` | 注册（diag_users） |
| `/diagnostic/login` | 登录（diag_sessions + cookie） |
| `/diagnostic/exams` | 选择竞赛与已发布试卷 |
| `/diagnostic/exams/<exam_id>/start` | 创建 attempt 并进入答题 |
| `/diagnostic/attempt/<attempt_id>?q=0` | 答题页（一题一页，计时、跳题、保存） |
| `/diagnostic/report/<attempt_id>` | 报告页 |
| `/diagnostic/practice/<practice_set_id>` | 练习包页 |
| `/admin/diagnostic/exams` | 诊断试卷列表 |
| `/admin/diagnostic/import` | 导入 CSV |
| `/admin/diagnostic/exams/<id>` | 卷子详情 |
| `/admin/diagnostic/questions/<id>` | 单题配置（知识点、练习来源、随机题数、压轴题） |
| `/admin/diagnostic/search/kp` | 知识点搜索（JSON，仅后台用） |
| `/admin/diagnostic/search/lessons` | 作业/课程搜索（JSON，仅后台用） |

---

## 四、CSV 导入列说明

- **试卷**：`competition` / `competition_name`、`exam_title`、`time_limit_sec`（可选）
- **题目**：`q_index`、`stem_text` / `stem`、`choices_json` 或 `choice_A`…、`answer_key` / `answer`、`solution_text` / `solution`、`kp_primary_id`、`kp_secondary_ids`（逗号分隔）、`practice_count_default`（默认 3）
- **题库（每题最多 3 道）**：`bank_p1_stem`、`bank_p1_choices`、`bank_p1_answer`，以及 `bank_p2_*`、`bank_p3_*`

编码需为 **UTF-8**。

---

## 五、测试 Checklist

- [ ] 迁移：`flask db upgrade` 仅新增 `diag_*` 表，无 ALTER 旧表
- [ ] 后台：管理员登录主系统 → 点击「诊断管理」→ 导入 CSV → 自动生成竞赛、试卷、题目、知识点、题库与练习配置
- [ ] 后台：试卷列表创建/删除/发布；卷子详情查看题目顺序；单题配置页修改知识点、练习来源、随机题数、压轴题
- [ ] 前台：/diagnostic 注册 → 登录 → 选择已发布试卷 → 开始答题
- [ ] 答题页：题号导航、上一题/下一题、交卷；计时与刷新后答案不丢（后端 + localStorage）
- [ ] 交卷后：报告页正确率、总耗时、错题知识点、答题详情；可进入练习包
- [ ] 练习包：题目来自 bank 或作业题库（依单题配置）
- [ ] 主系统：班级、课程、用户、作业答题等原有功能与数据未被修改

---

## 六、自检：未修改的旧逻辑

- **未修改**：任何现有表结构、现有路由、现有业务逻辑（班级/课程/用户/作业/QuizHistory/UserAnswer 等）
- **仅新增**：上述新文件、新表、新蓝图、新路由、新模板，以及 admin 导航中**一条**「诊断管理」链接

作业题库为**只读**接入：`homework_assignment_random` / `homework_curated_ids` 仅从 `Lesson` + `Question` 查询与随机抽样，不写入、不 ALTER 旧表。
