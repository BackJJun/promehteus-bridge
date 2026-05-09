-- QWEN 모델
INSERT INTO model_info
(model_id,
 model_name,
 model_class,
 model_provider,
 model_roles,
 api_base_url,
 open_source_yn)
VALUES ('Qwen/Qwen3-Coder-30B-A3B-Instruct',
        'Qween3-coder',
        'llm',
        'vllm',
        '[
          "chat",
          "edit",
          "apply",
          "autocomplete"
        ]'::jsonb,
        'http://localhost:8000/v1',
        'y');


-- GPT OSS 120B 모델
INSERT INTO model_info
(model_id,
 model_name,
 model_class,
 model_provider,
 model_roles,
 api_base_url,
 open_source_yn)
VALUES ('openai/gpt-oss-120b',
        'GPT OSS 120B',
        'llm',
        'openai',
        '[
          "chat",
          "edit",
          "apply",
          "autocomplete"
        ]'::jsonb,
        'http://localhost:8000/v1',
        'y');


-- 클로드 모델
INSERT INTO model_info
(model_id,
 model_name,
 model_class,
 model_provider,
 model_roles,
 api_key,
 api_base_url,
 open_source_yn)
VALUES ('claude-sonnet-4-5',
        'Claude Sonnet 4.5',
        'llm',
        'anthropic',
        '[
          "chat"
        ]'::jsonb,
        '',
        NULL,
        'n');

-- GEMINI 모델
INSERT INTO model_info
(model_id,
 model_name,
 model_class,
 model_provider,
 model_roles,
 api_key,
 api_base_url,
 open_source_yn)
VALUES ('gemini-3-flash-preview',
        'gemini-3-flash-preview',
        'llm',
        'gemini',
        '[
          "chat"
        ]'::jsonb,
        '',
        'http://localhost:8000/v1',
        'y');


-- 가짜 모델 (오류 유발용)
INSERT INTO model_info
(model_id,
 model_name,
 model_class,
 model_provider,
 model_roles,
 api_base_url,
 open_source_yn)
VALUES ('Gajja/Fake-kkk-30B-A3B-Instruct',
        'Gajja-fake-coder',
        'llm',
        'openai',
        '[
          "chat",
          "edit",
          "apply",
          "autocomplete"
        ]'::jsonb,
        'http://localhost:8000/v1',
        'y');
