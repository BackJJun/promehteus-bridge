import json
import os
import subprocess
import tempfile
import traceback

from fastapi import UploadFile, File, HTTPException, APIRouter
from loguru import logger
from starlette.requests import Request

import config
from src.db import dao_models
from src.llm_provider import get_provider

SECURE_BEARER_BIN_PATH = config.SECURE_BEARER_BIN_PATH
SECURE_BEARER_RULE_PATH = config.SECURE_BEARER_RULE_PATH

scan_router = APIRouter(prefix="/scan", tags=["scan"])


@scan_router.post("")
async def check_security(
        file: UploadFile = File(...)
):
    """소스코드 파일을 전달 받아서 보안 검사 실행"""
    try:
        # 확장자 추출 (분석 도구 도움을 위해 유지)
        suffix = os.path.splitext(file.filename)[1]

        # 1. 안전한 임시 파일 생성 (Linux/Unix 호환: with 블록 종료 시 자동 삭제)
        # Windows에서는 파일이 열린 상태에서 subprocess가 접근 불가할 수 있으나, 비-Windows 환경을 전제로 함
        with tempfile.NamedTemporaryFile(suffix=suffix, mode='wb') as tmp_file:
            # 2. 클라이언트로부터 받은 내용을 씁니다.
            content = await file.read()
            tmp_file.write(content)
            tmp_file.flush()  # 데이터가 물리 디스크(또는 버퍼)에 기록되도록 함

            logger.info(f"Scanning target: {tmp_file.name}")

            # 3. 외부 바이너리(check_secure) 실행
            # 명령행 형태: ~/bin/check_secure [temp_file_path]
            abs_bin_path = os.path.abspath(SECURE_BEARER_BIN_PATH)
            abs_rule_path = os.path.abspath(SECURE_BEARER_RULE_PATH)

            logger.info(f"Binary Path: {abs_bin_path} (Exists: {os.path.exists(abs_bin_path)})")
            logger.info(f"Rule Path: {abs_rule_path} (Exists: {os.path.exists(abs_rule_path)})")

            if os.path.exists(abs_rule_path):
                try:
                    rule_files = os.listdir(abs_rule_path)
                    logger.info(f"Rule Path Content Count: {len(rule_files)}")
                except Exception as e:
                    logger.error(f"Failed to list rule path: {e}")

            logger.info(f"Target File: {tmp_file.name}")

            cmd = [
                abs_bin_path, "scan", tmp_file.name,
                "--disable-default-rules",
                "--external-rule-dir=" + abs_rule_path,
                "--quiet",
                "--hide-progress-bar",
                "--format", "json"
            ]
            logger.info(f"Executing command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            # 4. 결과 반환
            logger.info(f"STDOUT: {result.stdout}")
            logger.info(f"STDERR: {result.stderr}")
            logger.info(f"Return Code: {result.returncode}")

            output_data = result.stdout
            try:
                if result.stdout:
                    output_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.warning("Failed to parse output as JSON")

            return {
                "filename": file.filename,
                'output': output_data,
                'error': result.stderr,
                'exit_code': result.returncode,
                'success': result.returncode == 0
            }

    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))



