-- =====================================================================
-- 项目管理系统 (PM-System) · 种子数据
-- 依据：架构设计文档 V1.2 §4 / §6
-- 内容：
--   1. 初始管理员账号
--   2. 内置 TR1~TR6 标准节点模板（华为 IPD 技术评审）
--   3. 系统默认配置（AI / 提醒 / 周界 / 审计保留期 / 附件）
-- 说明：幂等（用 ON CONFLICT 防重复），可重复执行。
-- ⚠️ 管理员初始密码哈希请务必在部署时替换（见下方说明）。
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. 初始管理员
--    密码哈希为 bcrypt("admin123") 的示例值，**部署时必须替换为正式密码的 bcrypt 散列**。
--    生成方式（Python）：
--      python -c "import bcrypt;print(bcrypt.hashpw(b'你的密码',bcrypt.gensalt()).decode())"
--    替换下面的 $2b$... 字符串即可。
-- ---------------------------------------------------------------------
INSERT INTO "user" (username, password_hash, display_name, role, status)
VALUES (
    'admin',
    '$2b$12$AyKOmbN/h4T9SZsqzUKosO0TTnLlxCfA3JsB0zU/zUobqSSJZ/Ip.',  -- TODO: 替换
    '系统管理员',
    'admin',
    'active'
)
ON CONFLICT (username) DO NOTHING;

-- ---------------------------------------------------------------------
-- 2. 内置 TR1~TR6 标准节点模板
--    评审要素（review_focus）为通用参考基线，组内可在"系统管理-模板"按实际调整或派生。
-- ---------------------------------------------------------------------
INSERT INTO tr_template (id, name, description, is_builtin, status)
VALUES (1, '标准TR1~TR6', '华为 IPD 技术评审标准节点模板（研发型项目默认）', TRUE, 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tr_template_node (template_id, node_key, name, sequence, review_focus) VALUES
(1, 'TR1', '概念/需求评审', 1,
 '评审焦点：产品包需求是否清晰、完整、可验证；需求来源与价值明确；初步可行性（技术/资源/周期）评估。
准入：需求文档/立项材料齐备。准出：需求基线确认，主要疑问闭环。'),
(1, 'TR2', '计划/方案评审', 2,
 '评审焦点：总体技术方案与架构是否合理；规格分解完整；项目计划（里程碑/资源/风险）可行。
准入：方案与计划文档齐备。准出：方案基线与计划基线确认。'),
(1, 'TR3', '开发前评审', 3,
 '评审焦点：详细设计/模块设计是否就绪；接口定义清晰；可测试性、可实现性评估。
准入：详细设计文档齐备。准出：设计冻结，进入开发。'),
(1, 'TR4', '开发/测试评审', 4,
 '评审焦点：编码实现与单元/集成测试（如 SDV/SIT）是否达标；缺陷收敛；功能完整性。
准入：代码与测试报告齐备。准出：达到提测/转测准则。'),
(1, 'TR5', '发布前评审', 5,
 '评审焦点：是否满足发布/验证（如 SVT）准则；遗留问题与风险可控；发布材料（文档/包/说明）齐备。
准入：验证报告齐备。准出：允许发布/交付。'),
(1, 'TR6', '量产/收尾评审', 6,
 '评审焦点：可交付性与可维护性；经验教训与复盘；资料归档完整。
准入：收尾材料齐备。准出：项目收尾/关闭。')
ON CONFLICT (template_id, node_key) DO NOTHING;

-- ---------------------------------------------------------------------
-- 3. 系统默认配置
-- ---------------------------------------------------------------------
INSERT INTO config (key, value, description) VALUES
('report.week_start_dow', '1',            '周界：一周起始日（1=周一 … 7=周日），默认周一'),
('ai.base_url',           '',             'OpenAI 兼容 API 的 base_url（部署时填写）'),
('ai.model',              'gpt-4o-mini',  'AI 绩效总结使用的模型名'),
('ai.api_key_ref',        'env:AI_API_KEY','AI Key 引用（从环境变量读取，不入库不返回前端）'),
('ai.timeout_seconds',    '60',           'AI 调用超时（秒）'),
('ai.max_retries',        '2',            'AI 调用失败重试次数'),
('ai.prompt_version',     'v1',           '绩效总结 Prompt 模板版本'),
('reminder.unfilled_cron','0 18 * * 1-5', '未填报提醒触发时间（工作日 18:00）'),
('reminder.overdue_cron', '0 9 * * *',    '逾期任务/节点检测时间（每日 09:00）'),
('reminder.risk_window_days', '7',        '看板 at_risk 判定的风险时效窗口（天）'),
('audit.retention_months','24',           '审计日志保留期（月），到期归档/清理'),
('attachment.max_mb',     '50',           '附件单文件大小上限（MB）'),
('attachment.allowed_ext','pdf,doc,docx,xls,xlsx,ppt,pptx,txt,md,png,jpg,jpeg,zip', '附件类型白名单'),
('backup.keep_count',     '14',           '备份保留份数'),
('security.login_max_fail','5',           '连续登录失败锁定阈值'),
('security.lock_minutes', '15',           '登录锁定时长（分钟）'),
('security.jwt_access_ttl_min', '120',    'access token 有效期（分钟）'),
('security.jwt_refresh_ttl_day','7',      'refresh token 有效期（天）')
ON CONFLICT (key) DO NOTHING;

COMMIT;

-- =====================================================================
-- 完成。内置模板与默认配置已就绪。
-- 提示：管理员密码哈希务必替换；AI base_url/api_key 部署时配置。
-- =====================================================================
