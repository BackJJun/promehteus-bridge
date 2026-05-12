-- 채팅 내용 메타 데이터(세션)
CREATE TABLE chat_session_info
(
    chat_id             BIGSERIAL PRIMARY KEY,
    session_id          VARCHAR(100) UNIQUE NOT NULL,
    user_id             UUID                NOT NULL,
    title               VARCHAR(500)        NOT NULL,
    workspace_directory VARCHAR(1000),
    date_created        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted          BOOLEAN   DEFAULT FALSE
);

CREATE INDEX idx_chat_sessions_user_id ON chat_session_info (user_id);
CREATE INDEX idx_chat_sessions_session_id ON chat_session_info (session_id);
CREATE INDEX idx_chat_sessions_date_created ON chat_session_info (date_created DESC);
CREATE INDEX idx_chat_sessions_user_date ON chat_session_info (user_id, date_created DESC);

-- 채팅 내용 데이터
CREATE TABLE chat_history_info
(
    id            BIGSERIAL PRIMARY KEY,
    chat_id       BIGINT NOT NULL,
    message_index INT    NOT NULL,
    message_data  JSONB  NOT NULL, -- 전체 history item을 JSON으로 저장
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (chat_id) REFERENCES chat_session_info (chat_id) ON DELETE CASCADE,
    UNIQUE (chat_id, message_index)
);

CREATE INDEX idx_chat_history_session_id ON chat_history_info (chat_id);
CREATE INDEX idx_chat_history_session_index ON chat_history_info (chat_id, message_index);

CREATE TABLE chat_ui_message_info
(
    id                 BIGSERIAL PRIMARY KEY,
    chat_id            BIGINT      NOT NULL,
    ui_message_index   INT         NOT NULL,
    source_start_index INT,
    source_end_index   INT,
    message_type       VARCHAR(50) NOT NULL,
    display_role       VARCHAR(30),
    message_data       JSONB       NOT NULL,
    view_version       INT         NOT NULL DEFAULT 1,
    created_at         TIMESTAMP            DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP            DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (chat_id) REFERENCES chat_session_info (chat_id) ON DELETE CASCADE,
    UNIQUE (chat_id, ui_message_index, view_version)
);

CREATE INDEX idx_chat_ui_message_chat_version
ON chat_ui_message_info (chat_id, view_version, ui_message_index);

CREATE INDEX idx_chat_ui_message_type
ON chat_ui_message_info (message_type);

CREATE TABLE chat_ui_projection_info
(
    chat_id              BIGINT      NOT NULL,
    view_version         INT         NOT NULL,
    source_message_count INT         NOT NULL,
    source_updated_at    TIMESTAMP,
    build_status         VARCHAR(30) NOT NULL,
    error_message        TEXT,
    built_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (chat_id) REFERENCES chat_session_info (chat_id) ON DELETE CASCADE,
    PRIMARY KEY (chat_id, view_version)
);

-- 채팅 이미지 데이터
CREATE TABLE chat_image_info (
    image_id UUID PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    message_index INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    filename VARCHAR(255),
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    original_width INTEGER,
    original_height INTEGER,
    storage_path TEXT NOT NULL,
    sha256 VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chat_image_info_session_message
ON chat_image_info (chat_id, message_index, sort_order);

CREATE TABLE chat_last_session
(
    user_id             UUID          NOT NULL,
    workspace_directory VARCHAR(1000) NOT NULL,
    session_id          VARCHAR(100)  NOT NULL,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, workspace_directory)
);


-- 아래는 참조용 --
CREATE TABLE model_info
(
    id             SERIAL PRIMARY KEY,
    model_id       VARCHAR(40),
    model_name     VARCHAR(80) NOT NULL,
    model_class    VARCHAR(20) NOT NULL,
    model_provider VARCHAR(30) NOT NULL,
    model_roles    JSONB       NOT NULL,
    api_key        VARCHAR NULL,
    api_base_url   VARCHAR NULL,
    is_active      BOOLEAN     NOT NULL DEFAULT true,
    open_source_yn VARCHAR(30) NOT NULL DEFAULT 'n',
    reg_time       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
