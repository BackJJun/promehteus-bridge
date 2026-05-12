CREATE TABLE IF NOT EXISTS chat_ui_message_info
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

CREATE INDEX IF NOT EXISTS idx_chat_ui_message_chat_version
ON chat_ui_message_info (chat_id, view_version, ui_message_index);

CREATE INDEX IF NOT EXISTS idx_chat_ui_message_type
ON chat_ui_message_info (message_type);

CREATE TABLE IF NOT EXISTS chat_ui_projection_info
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

