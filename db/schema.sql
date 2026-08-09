-- =====================================================================
-- 项目管理系统 (PM-System) · PostgreSQL 建库脚本
-- 依据：架构设计文档 V1.2 §4
-- 说明：
--   * 主键统一 BIGSERIAL（自增 BIGINT）
--   * 业务表软删：is_deleted + deleted_at（见架构 §4.2.0）
--   * 软删兼容的唯一约束一律用"部分唯一索引 (WHERE NOT is_deleted)"
--   * 进展表唯一索引用表达式 COALESCE(project_node_id,0) 处理 NULL 语义
-- 适用：PostgreSQL 14+
-- 执行顺序：本文件自上而下（外键依赖已按序排列）
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. 用户与认证
-- ---------------------------------------------------------------------
CREATE TABLE "user" (
    id                 BIGSERIAL PRIMARY KEY,
    username           VARCHAR(64)  NOT NULL,
    password_hash      VARCHAR(255) NOT NULL,
    display_name       VARCHAR(64)  NOT NULL,
    email              VARCHAR(128),
    role               VARCHAR(16)  NOT NULL DEFAULT 'member',   -- admin / member
    status             VARCHAR(16)  NOT NULL DEFAULT 'active',   -- active / disabled
    failed_login_count INT          NOT NULL DEFAULT 0,
    locked_until       TIMESTAMPTZ,
    last_login_at      TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_user_username ON "user"(username);
COMMENT ON TABLE  "user" IS '用户表';
COMMENT ON COLUMN "user".role IS '系统角色：admin/member（项目负责人为项目级，见 project_member）';

-- refresh_token 持久化（登出/强制重登可吊销）
CREATE TABLE auth_token (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    refresh_token_hash VARCHAR(255) NOT NULL,
    expires_at        TIMESTAMPTZ NOT NULL,
    revoked           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_auth_token_user ON auth_token(user_id);
COMMENT ON TABLE auth_token IS '刷新令牌（吊销实现登出/强制重登）';

-- 密码重置（内网：管理员重置）
CREATE TABLE password_reset (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    reset_by          BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    new_password_hash VARCHAR(255) NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_password_reset_user ON password_reset(user_id);
COMMENT ON TABLE password_reset IS '密码重置记录（管理员重置成员密码）';

-- ---------------------------------------------------------------------
-- 2. 项目与成员
-- ---------------------------------------------------------------------
CREATE TABLE project (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    code            VARCHAR(64)  NOT NULL,
    machine_model   VARCHAR(64),                                -- 机型
    owner_id        BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    status          VARCHAR(16)  NOT NULL DEFAULT 'not_started',-- not_started/in_progress/delayed/completed/suspended（手动配置，已完成即终态）
    health          VARCHAR(16)  NOT NULL DEFAULT 'on_track',   -- on_track/at_risk/delayed（终态冻结，见§5.2）
    current_node_id BIGINT,                                     -- 当前TR节点（冗余，FK在 project_node 建好后补）
    start_date      DATE,
    end_date        DATE,
    description     TEXT,
    created_by      BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_project_code  ON project(code)  WHERE NOT is_deleted;
CREATE UNIQUE INDEX ux_project_name  ON project(name)  WHERE NOT is_deleted;
CREATE INDEX ix_project_status  ON project(status)       WHERE NOT is_deleted;
CREATE INDEX ix_project_owner   ON project(owner_id)     WHERE NOT is_deleted;
CREATE INDEX ix_project_machine ON project(machine_model) WHERE NOT is_deleted;

-- 机型管理（管理端维护；新建/编辑项目下拉选择）
CREATE TABLE machine_model (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(64) NOT NULL,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_machine_model_name ON machine_model(name) WHERE NOT is_deleted;
COMMENT ON TABLE project IS '项目表';

CREATE TABLE project_member (
    id           BIGSERIAL PRIMARY KEY,
    project_id   BIGINT NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    project_role VARCHAR(32),                              -- 项目角色：负责人/开发/测试/…
    is_invested  BOOLEAN NOT NULL DEFAULT TRUE,            -- 当前是否投入
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_member ON project_member(project_id, user_id) WHERE NOT is_deleted;
CREATE INDEX ix_member_user   ON project_member(user_id) WHERE NOT is_deleted;  -- 查"我参与的项目/按人周报/绩效"
COMMENT ON TABLE project_member IS '项目成员（project.owner_id 必须也在此表，应用层保证）';

CREATE TABLE project_role_assignment (
    id           BIGSERIAL PRIMARY KEY,
    project_id   BIGINT NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
    role         VARCHAR(32) NOT NULL,                     -- SE / TPM / TL/FO / CodeReview
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_project_role_assignment_role CHECK (role IN ('SE', 'TPM', 'TL/FO', 'CodeReview')),
    CONSTRAINT ux_project_role_assignment UNIQUE (project_id, role, user_id)
);
CREATE INDEX ix_project_role_assignment_project ON project_role_assignment(project_id);
CREATE INDEX ix_project_role_assignment_user ON project_role_assignment(user_id);
COMMENT ON TABLE project_role_assignment IS '项目固定角色分配';

-- ---------------------------------------------------------------------
-- 3. TR 模板与项目节点
-- ---------------------------------------------------------------------
CREATE TABLE tr_template (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(128) NOT NULL,
    description TEXT,
    is_builtin  BOOLEAN NOT NULL DEFAULT FALSE,            -- 内置模板禁删/禁改名
    status      VARCHAR(16) NOT NULL DEFAULT 'active',
    created_by  BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_tr_template_name ON tr_template(name);
COMMENT ON TABLE tr_template IS 'TR节点模板（如 标准TR1~TR6）';

CREATE TABLE tr_template_node (
    id            BIGSERIAL PRIMARY KEY,
    template_id   BIGINT NOT NULL REFERENCES tr_template(id) ON DELETE CASCADE,
    node_key      VARCHAR(16) NOT NULL,                    -- TR1~TR6 / 自定义键
    name          VARCHAR(64) NOT NULL,
    sequence      INT NOT NULL,
    review_focus  TEXT                                     -- 评审要素/准入准出
);
CREATE UNIQUE INDEX ux_ttn_key ON tr_template_node(template_id, node_key);
CREATE UNIQUE INDEX ux_ttn_seq ON tr_template_node(template_id, sequence);
COMMENT ON TABLE tr_template_node IS '模板节点';

CREATE TABLE project_node (
    id               BIGSERIAL PRIMARY KEY,
    project_id       BIGINT NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
    template_node_id BIGINT REFERENCES tr_template_node(id) ON DELETE SET NULL, -- 追溯用
    node_key         VARCHAR(16) NOT NULL,
    name             VARCHAR(64) NOT NULL,
    sequence         INT NOT NULL,
    status           VARCHAR(16) NOT NULL DEFAULT 'not_started', -- not_started/in_progress/pending_review/passed/failed
    planned_start    DATE,
    planned_end      DATE,
    actual_start     DATE,
    actual_end       DATE,
    is_deleted       BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_node_seq ON project_node(project_id, sequence) WHERE NOT is_deleted;
COMMENT ON TABLE project_node IS '项目TR节点实例（rectifying 为派生展示标记，见§5.3）';

-- project.current_node_id 外键（环形依赖，后补）
ALTER TABLE project
    ADD CONSTRAINT fk_project_current_node
    FOREIGN KEY (current_node_id) REFERENCES project_node(id) ON DELETE SET NULL;

CREATE TABLE node_review (
    id              BIGSERIAL PRIMARY KEY,
    project_node_id BIGINT NOT NULL REFERENCES project_node(id) ON DELETE RESTRICT,
    conclusion      VARCHAR(16) NOT NULL,                  -- pass / conditional_pass / fail
    reviewer_id     BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    review_date     DATE NOT NULL,
    comment         TEXT,                                  -- 评审意见/遗留问题说明
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    -- 只增不删
);
CREATE INDEX ix_node_review_node ON node_review(project_node_id);
COMMENT ON TABLE node_review IS '节点评审记录（一节点可多次评审，只增不删）';

-- ---------------------------------------------------------------------
-- 4. 任务
-- ---------------------------------------------------------------------
CREATE TABLE task (
    id               BIGSERIAL PRIMARY KEY,
    project_node_id  BIGINT NOT NULL REFERENCES project_node(id) ON DELETE RESTRICT,
    project_id       BIGINT NOT NULL REFERENCES project(id)      ON DELETE RESTRICT, -- 冗余，须与 node.project_id 一致
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    assignee_id      BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    status           VARCHAR(16) NOT NULL DEFAULT 'todo',        -- todo/in_progress/done（overdue 派生）
    planned_start    DATE,
    planned_end      DATE,
    actual_end       DATE,                                       -- 实际完成时间
    source_review_id BIGINT REFERENCES node_review(id) ON DELETE SET NULL, -- 来源评审问题项
    created_by       BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    is_deleted       BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_task_node     ON task(project_node_id, status) WHERE NOT is_deleted;
CREATE INDEX ix_task_assignee ON task(assignee_id, status)     WHERE NOT is_deleted;
CREATE INDEX ix_task_project  ON task(project_id, status)      WHERE NOT is_deleted;
COMMENT ON TABLE task IS '任务（完成情况跟踪：是否完成 + 计划/实际时间；延期为派生）';

-- ---------------------------------------------------------------------
-- 5. 进展（项目/节点级 · 多人协作）
-- ---------------------------------------------------------------------
CREATE TABLE progress (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
    project_node_id BIGINT REFERENCES project_node(id) ON DELETE RESTRICT, -- 可空=项目级进展
    author_id       BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    progress_date   DATE NOT NULL,                           -- 业务日期（按此聚合周报）
    today_work      TEXT NOT NULL,
    tomorrow_plan   TEXT,
    risk            TEXT,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 防"一人一天重复填报"：项目级一条 + 各节点各一条 / 人 / 天；COALESCE 处理 node NULL
CREATE UNIQUE INDEX uq_progress ON progress
    (author_id, project_id, COALESCE(project_node_id, 0), progress_date)
    WHERE NOT is_deleted;
CREATE INDEX ix_progress_proj_date   ON progress(project_id, progress_date) WHERE NOT is_deleted;
CREATE INDEX ix_progress_author_date ON progress(author_id, progress_date) WHERE NOT is_deleted;
COMMENT ON TABLE progress IS '进展（项目/节点级多人协作；按 progress_date 聚合周报）';

CREATE TABLE progress_task_link (
    id          BIGSERIAL PRIMARY KEY,
    progress_id BIGINT NOT NULL REFERENCES progress(id) ON DELETE CASCADE,
    task_id     BIGINT NOT NULL REFERENCES task(id)     ON DELETE CASCADE  -- task.project_id 须等于 progress.project_id（应用层校验）
);
CREATE UNIQUE INDEX ux_ptl ON progress_task_link(progress_id, task_id);
CREATE INDEX ix_ptl_task ON progress_task_link(task_id);                   -- 反查任务被哪些进展引用
COMMENT ON TABLE progress_task_link IS '进展-任务关联';

-- ---------------------------------------------------------------------
-- 6. 周目标
-- ---------------------------------------------------------------------
CREATE TABLE project_weekly_goal (
    id          BIGSERIAL PRIMARY KEY,
    project_id  BIGINT NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
    week_start  DATE NOT NULL,                             -- 本周起始日（应用层按周界规整）
    goal        TEXT NOT NULL,
    set_by      BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_weekly_goal ON project_weekly_goal(project_id, week_start) WHERE NOT is_deleted;
COMMENT ON TABLE project_weekly_goal IS '项目周目标（周报头部）';

-- ---------------------------------------------------------------------
-- 7. 附件
-- ---------------------------------------------------------------------
CREATE TABLE attachment (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT NOT NULL REFERENCES project(id) ON DELETE RESTRICT, -- 须与所挂对象同项目
    project_node_id BIGINT REFERENCES project_node(id) ON DELETE RESTRICT,
    task_id         BIGINT REFERENCES task(id)        ON DELETE RESTRICT,
    review_id       BIGINT REFERENCES node_review(id) ON DELETE RESTRICT,
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(512) NOT NULL,
    file_size       BIGINT,
    mime_type       VARCHAR(64),
    uploaded_by     BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT ck_attachment_owner CHECK (
        project_node_id IS NOT NULL OR task_id IS NOT NULL OR review_id IS NOT NULL
    )
);
CREATE INDEX ix_attachment_project ON attachment(project_id)      WHERE NOT is_deleted;
CREATE INDEX ix_attachment_node    ON attachment(project_node_id) WHERE NOT is_deleted;
CREATE INDEX ix_attachment_task    ON attachment(task_id)         WHERE NOT is_deleted;
CREATE INDEX ix_attachment_review  ON attachment(review_id)       WHERE NOT is_deleted;
COMMENT ON TABLE attachment IS '附件（至少关联 node/task/review 之一）';

-- ---------------------------------------------------------------------
-- 8. AI 绩效总结
-- ---------------------------------------------------------------------
CREATE TABLE ai_summary (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    period_type     VARCHAR(8) NOT NULL,                   -- month / quarter / year
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    content         TEXT,                                  -- AI 原始总结
    edited_content  TEXT,                                  -- 人工编辑版（考核以此为准）
    source_snapshot JSONB,                                 -- {period, prompt_version, model_params, items:[{type,id,excerpt}]}
    model           VARCHAR(64),
    status          VARCHAR(16) NOT NULL DEFAULT 'generating', -- generating/generated/edited/failed
    error           VARCHAR(255),
    generated_by    BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_ai_summary ON ai_summary(user_id, period_type, period_start);
COMMENT ON TABLE ai_summary IS 'AI 绩效总结（同周期覆盖式更新；generating 占位防并发）';

-- ---------------------------------------------------------------------
-- 9. 审计 / 配置 / 通知
-- ---------------------------------------------------------------------
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    BIGINT REFERENCES "user"(id) ON DELETE RESTRICT,
    action      VARCHAR(32) NOT NULL,                      -- create/update/delete/review/force_transition/login/import/config_change/export/reset_password/backup
    target_type VARCHAR(32),
    target_id   VARCHAR(64),
    detail      JSONB,                                     -- 变更字段 diff（仅变化字段）
    ip          VARCHAR(45),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    -- 只增不删；保留期定期归档/清理
);
CREATE INDEX ix_audit_target ON audit_log(target_type, target_id);
CREATE INDEX ix_audit_actor  ON audit_log(actor_id, created_at);
CREATE INDEX ix_audit_time   ON audit_log(created_at);
COMMENT ON TABLE audit_log IS '审计日志（只增不删，设保留期）';

CREATE TABLE config (
    key         VARCHAR(64) PRIMARY KEY,
    value       TEXT,
    description VARCHAR(255),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE config IS '系统配置（ai.* / reminder.* / report.week_start_dow / audit.retention_months 等）';

CREATE TABLE notification (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    type       VARCHAR(32) NOT NULL,                       -- unfilled/overdue/review/…
    title      VARCHAR(255) NOT NULL,
    content    TEXT,
    link       VARCHAR(255),
    ref_type   VARCHAR(32),
    ref_id     BIGINT,
    dedup_key  VARCHAR(128),                               -- 防重键（type+user+ref+日期）
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_notification_dedup ON notification(dedup_key);
CREATE INDEX ix_notification_user ON notification(user_id, is_read);
COMMENT ON TABLE notification IS '通知（定时任务产生，dedup_key 防重复）';

COMMIT;

-- =====================================================================
-- 完成。下一步执行 seed.sql 写入内置 TR 模板/管理员/默认配置。
-- =====================================================================
