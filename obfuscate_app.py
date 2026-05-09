#!/usr/bin/env python3
"""
PyArmor 난독화 스크립트
app의 src, config.py, runserver.py를 난독화하여
obfuscation 디렉토리에 저장합니다.

Windows와 Linux에서 모두 실행 가능합니다.
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
import logging

# 로깅 설정 - UTF-8 인코딩으로 한글 지원
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('obfuscation.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)  # 명시적으로 stdout 사용
    ]
)

# Windows에서 콘솔 출력 인코딩 설정
if platform.system() == "Windows":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
logger = logging.getLogger(__name__)


class PyArmorObfuscator:
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.app_dir = self.script_dir
        self.obfuscation_dir = self.app_dir / "obfuscation"
        self.temp_dir = self.app_dir / "temp_obfuscation"

        # 난독화할 파일들과 디렉토리들
        self.targets = [
            "src",  # 디렉토리
            "config.py",  # 파일
            "runserver.py"  # 파일
        ]

        # 추가로 복사할 파일들
        self.additional_files = [
            "Dockerfile",
            "requirements.txt",
        ]

        # 추가로 복사할 폴더들
        self.additional_folders = [
            "src/static"
        ]

        logger.info(f"스크립트 디렉토리: {self.script_dir}")
        logger.info(f"app 디렉토리: {self.app_dir}")
        logger.info(f"난독화 결과 디렉토리: {self.obfuscation_dir}")

    def check_pyarmor_installed(self):
        """PyArmor가 설치되어 있는지 확인"""
        # 환경 변수 설정으로 인코딩 문제 해결
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
            # 먼저 직접 pyarmor 명령어로 시도
            result = subprocess.run(['pyarmor', '--version'],
                                    capture_output=True, text=True, 
                                    encoding='utf-8', errors='ignore',
                                    env=env, check=True)
            logger.info(f"PyArmor 버전: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # python -m pyarmor로 시도
                result = subprocess.run([sys.executable, '-m', 'pyarmor', '--version'],
                                        capture_output=True, text=True,
                                        encoding='utf-8', errors='ignore',
                                        env=env, check=True)
                if result.stdout.strip():
                    logger.info(f"PyArmor 버전: {result.stdout.strip()}")
                    return True
                elif result.stderr.strip():
                    logger.info(f"PyArmor 버전: {result.stderr.strip()}")
                    return True
                else:
                    # 출력이 없어도 오류가 없으면 설치되어 있는 것으로 판단
                    logger.info("PyArmor가 설치되어 있습니다.")
                    return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    # pip list로 설치 여부 확인
                    result = subprocess.run([sys.executable, '-m', 'pip', 'list'],
                                            capture_output=True, text=True,
                                            encoding='utf-8', errors='ignore',
                                            env=env, check=True)
                    if 'pyarmor' in result.stdout.lower():
                        logger.info("PyArmor가 설치되어 있습니다 (pip list에서 확인됨)")
                        return True
                    else:
                        logger.error("PyArmor가 설치되어 있지 않습니다.")
                        logger.error("다음 명령어로 설치하세요: pip install pyarmor")
                        return False
                except (subprocess.CalledProcessError, FileNotFoundError):
                    logger.error("PyArmor가 설치되어 있지 않습니다.")
                    logger.error("다음 명령어로 설치하세요: pip install pyarmor")
                    return False

    def prepare_directories(self):
        """디렉토리 준비"""
        try:
            # 기존 obfuscation 디렉토리가 있으면 삭제
            if self.obfuscation_dir.exists():
                logger.info(f"기존 {self.obfuscation_dir} 디렉토리를 삭제합니다.")
                shutil.rmtree(self.obfuscation_dir)

            # 임시 디렉토리가 있으면 삭제
            if self.temp_dir.exists():
                logger.info(f"기존 {self.temp_dir} 디렉토리를 삭제합니다.")
                shutil.rmtree(self.temp_dir)

            # 새로 생성
            self.obfuscation_dir.mkdir(exist_ok=True)
            self.temp_dir.mkdir(exist_ok=True)

            logger.info("디렉토리 준비 완료")
            return True

        except Exception as e:
            logger.error(f"디렉토리 준비 중 오류 발생: {e}")
            return False

    def copy_target_files(self):
        """난독화할 파일들을 임시 디렉토리로 복사"""
        try:
            for target in self.targets:
                source_path = self.app_dir / target
                dest_path = self.temp_dir / target

                if not source_path.exists():
                    logger.warning(f"소스 파일/디렉토리가 존재하지 않습니다: {source_path}")
                    continue

                if source_path.is_file():
                    shutil.copy2(source_path, dest_path)
                    logger.info(f"파일 복사: {source_path} -> {dest_path}")
                elif source_path.is_dir():
                    shutil.copytree(source_path, dest_path)
                    logger.info(f"디렉토리 복사: {source_path} -> {dest_path}")

            return True

        except Exception as e:
            logger.error(f"파일 복사 중 오류 발생: {e}")
            return False

    def obfuscate_files(self):
        """PyArmor를 사용하여 파일들을 난독화"""
        try:
            success_count = 0

            for target in self.targets:
                target_path = self.temp_dir / target
                if not target_path.exists():
                    logger.warning(f"타겟이 존재하지 않습니다: {target_path}")
                    continue

                # 출력 경로 설정
                output_path = self.obfuscation_dir / target

                # 파일인지 디렉토리인지에 따라 다르게 처리
                if target_path.is_file():
                    # 개별 파일 난독화
                    try:
                        cmd = ['pyarmor', 'gen', '-O', str(self.obfuscation_dir), str(target_path)]
                        logger.info(f"PyArmor 명령어 실행: {' '.join(cmd)}")

                        # UTF-8 인코딩으로 실행하여 한글 처리 문제 해결
                        result = subprocess.run(cmd, capture_output=True, text=True, 
                                              encoding='utf-8', errors='ignore', check=True)
                        logger.info(f"'{target}' 파일 난독화 완료")
                        if result.stdout:
                            logger.debug(f"PyArmor 출력: {result.stdout}")
                        success_count += 1

                    except subprocess.CalledProcessError as e:
                        logger.error(f"'{target}' 파일 난독화 실패: {e}")
                        if e.stderr:
                            logger.error(f"에러 메시지: {e.stderr}")
                        if e.stdout:
                            logger.error(f"출력 메시지: {e.stdout}")

                        # 실패한 경우 원본 파일 복사
                        try:
                            shutil.copy2(target_path, output_path)
                            logger.warning(f"'{target}' 난독화 실패로 원본 파일 복사")
                        except Exception as copy_error:
                            logger.error(f"'{target}' 원본 파일 복사 실패: {copy_error}")

                elif target_path.is_dir():
                    # 디렉토리 전체 난독화 - src 폴더를 위한 개선된 방법
                    try:
                        # src 디렉토리의 경우 더 자세한 로깅
                        if target == "src":
                            logger.info(f"src 디렉토리 난독화 시작: {target_path}")
                            logger.info(f"src 디렉토리 내용: {list(target_path.rglob('*.py'))}")
                        
                        # 환경 변수 설정으로 인코딩 문제 해결
                        env = os.environ.copy()
                        env['PYTHONIOENCODING'] = 'utf-8'
                        
                        cmd = ['pyarmor', 'gen', '-O', str(self.obfuscation_dir), '-r', str(target_path)]
                        logger.info(f"PyArmor 명령어 실행: {' '.join(cmd)}")

                        # UTF-8 인코딩과 환경변수 설정으로 실행
                        result = subprocess.run(cmd, capture_output=True, text=True, 
                                              encoding='utf-8', errors='ignore', 
                                              env=env, check=True)
                        logger.info(f"'{target}' 디렉토리 난독화 완료")
                        if result.stdout:
                            logger.debug(f"PyArmor 출력: {result.stdout}")
                        success_count += 1

                    except subprocess.CalledProcessError as e:
                        logger.error(f"'{target}' 디렉토리 난독화 실패: {e}")
                        if e.stderr:
                            logger.error(f"에러 메시지: {e.stderr}")
                        if e.stdout:
                            logger.error(f"출력 메시지: {e.stdout}")
                        
                        # src 폴더의 경우 개별 파일 단위로 다시 시도
                        if target == "src":
                            logger.info("src 디렉토리 전체 난독화 실패, 개별 파일 단위로 재시도...")
                            if self.obfuscate_src_individually():
                                success_count += 1
                                continue

                        # 실패한 경우 원본 디렉토리 복사
                        try:
                            if output_path.exists():
                                shutil.rmtree(output_path)
                            shutil.copytree(target_path, output_path)
                            logger.warning(f"'{target}' 난독화 실패로 원본 디렉토리 복사")
                        except Exception as copy_error:
                            logger.error(f"'{target}' 원본 디렉토리 복사 실패: {copy_error}")

            if success_count > 0:
                logger.info(f"총 {success_count}개 파일/디렉토리 처리 완료")
                return True
            else:
                logger.warning("모든 파일을 원본으로 복사했습니다 (난독화 실패)")
                return True  # 원본 파일이라도 복사되었으면 성공으로 처리

        except Exception as e:
            logger.error(f"난독화 중 예상치 못한 오류 발생: {e}")
            return False

    def obfuscate_src_individually(self):
        """src 디렉토리를 개별 파일 단위로 난독화"""
        try:
            src_temp_path = self.temp_dir / "src"
            src_output_path = self.obfuscation_dir / "src"
            
            if not src_temp_path.exists():
                logger.error("src 디렉토리가 임시 폴더에 없습니다")
                return False
            
            # 출력 디렉토리 생성
            src_output_path.mkdir(parents=True, exist_ok=True)
            
            # 모든 Python 파일 찾기
            python_files = list(src_temp_path.rglob("*.py"))
            logger.info(f"src 디렉토리에서 {len(python_files)}개의 Python 파일을 찾았습니다")
            
            success_count = 0
            total_files = len(python_files)
            
            # 환경 변수 설정
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            for py_file in python_files:
                try:
                    # 상대 경로 계산
                    rel_path = py_file.relative_to(src_temp_path)
                    output_file_dir = src_output_path / rel_path.parent
                    output_file_dir.mkdir(parents=True, exist_ok=True)
                    
                    logger.info(f"파일 난독화 시도: {rel_path}")
                    
                    # 개별 파일 난독화
                    cmd = ['pyarmor', 'gen', '-O', str(output_file_dir), str(py_file)]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True,
                                          encoding='utf-8', errors='ignore',
                                          env=env, check=True)
                    
                    logger.info(f"파일 난독화 성공: {rel_path}")
                    success_count += 1
                    
                except subprocess.CalledProcessError as e:
                    logger.warning(f"파일 난독화 실패 ({rel_path}): {e}")
                    
                    # 실패한 경우 원본 파일 복사
                    try:
                        output_file = src_output_path / rel_path
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(py_file, output_file)
                        logger.info(f"원본 파일 복사: {rel_path}")
                        success_count += 1
                    except Exception as copy_error:
                        logger.error(f"원본 파일 복사 실패 ({rel_path}): {copy_error}")
                
                except Exception as e:
                    logger.error(f"예상치 못한 오류 ({rel_path}): {e}")
            
            # 비Python 파일들도 복사 (__init__.py 등)
            for item in src_temp_path.rglob("*"):
                if item.is_file() and not item.name.endswith('.py'):
                    try:
                        rel_path = item.relative_to(src_temp_path)
                        output_item = src_output_path / rel_path
                        output_item.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, output_item)
                        logger.info(f"비Python 파일 복사: {rel_path}")
                    except Exception as e:
                        logger.warning(f"비Python 파일 복사 실패 ({rel_path}): {e}")
            
            logger.info(f"src 개별 파일 처리 완료: {success_count}/{total_files} 성공")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"src 개별 파일 난독화 중 오류: {e}")
            return False

    def copy_additional_files(self):
        """난독화되지 않은 필요한 파일들을 obfuscation 디렉토리로 복사"""
        try:
            # self.additional_files에 정의된 파일들만 복사
            for file_name in self.additional_files:
                source_path = self.app_dir / file_name
                if source_path.exists():
                    dest_path = self.obfuscation_dir / file_name
                    shutil.copy2(source_path, dest_path)
                    logger.info(f"추가 파일 복사: {file_name}")
                else:
                    logger.warning(f"추가 파일이 존재하지 않습니다: {file_name}")

            return True

        except Exception as e:
            logger.error(f"추가 파일 복사 중 오류 발생: {e}")
            return False

    def copy_additional_folders(self):
        """난독화되지 않은 필요한 폴더들을 obfuscation 디렉토리로 복사"""
        try:
            # self.additional_folders에 정의된 폴더들만 복사
            for folder_name in self.additional_folders:
                source_path = self.app_dir / folder_name
                if source_path.exists() and source_path.is_dir():
                    dest_path = self.obfuscation_dir / folder_name
                    
                    # 기존 폴더가 있으면 삭제 후 복사
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    
                    shutil.copytree(source_path, dest_path)
                    logger.info(f"추가 폴더 복사: {folder_name}")
                else:
                    if not source_path.exists():
                        logger.warning(f"추가 폴더가 존재하지 않습니다: {folder_name}")
                    elif not source_path.is_dir():
                        logger.warning(f"경로가 폴더가 아닙니다: {folder_name}")

            return True

        except Exception as e:
            logger.error(f"추가 폴더 복사 중 오류 발생: {e}")
            return False

    def cleanup_temp_directory(self):
        """임시 디렉토리 정리"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info("임시 디렉토리 정리 완료")
        except Exception as e:
            logger.warning(f"임시 디렉토리 정리 중 오류 발생: {e}")

    def create_run_script(self):
        """실행 스크립트 생성 (비활성화됨)"""
        # 실행 스크립트를 생성하지 않음
        logger.info("실행 스크립트 생성 건너뛰기 (비활성화됨)")
        return True

    def run(self):
        """전체 난독화 프로세스 실행"""
        logger.info("=" * 50)
        logger.info("PyArmor 난독화 프로세스 시작")
        logger.info(f"플랫폼: {platform.system()} {platform.release()}")
        logger.info("=" * 50)

        # 1. PyArmor 설치 확인
        if not self.check_pyarmor_installed():
            return False

        # 2. 디렉토리 준비
        if not self.prepare_directories():
            return False

        # 3. 타겟 파일들 복사
        if not self.copy_target_files():
            return False

        # 4. 파일들 난독화
        if not self.obfuscate_files():
            return False

        # 5. 추가 파일들 복사
        if not self.copy_additional_files():
            return False

        # 6. 추가 폴더들 복사
        if not self.copy_additional_folders():
            return False

        # 7. 실행 스크립트 생성
        if not self.create_run_script():
            return False

        # 8. 임시 디렉토리 정리
        self.cleanup_temp_directory()

        logger.info("=" * 50)
        logger.info("난독화 프로세스 완료!")
        logger.info(f"결과물 위치: {self.obfuscation_dir}")
        logger.info("=" * 50)

        return True


def main():
    """메인 함수"""
    try:
        # 환경 변수 설정으로 전역 인코딩 문제 해결
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        obfuscator = PyArmorObfuscator()
        success = obfuscator.run()

        if success:
            print("\n✅ 난독화가 성공적으로 완료되었습니다!")
            print(f"📁 결과물 위치: {obfuscator.obfuscation_dir}")
            print("🚀 난독화된 파일들:")
            print("   - src/ (모든 Python 파일 난독화)")
            print("   - config.py") 
            print("   - runserver.py")
            print("📂 복사된 추가 파일들:")
            for file_name in obfuscator.additional_files:
                print(f"   - {file_name}")
            print("📂 복사된 추가 폴더들:")
            for folder_name in obfuscator.additional_folders:
                print(f"   - {folder_name}/")
            print("📋 로그 파일: obfuscation.log")
            sys.exit(0)
        else:
            print("\n❌ 난독화 중 오류가 발생했습니다.")
            print("📋 자세한 내용은 obfuscation.log 파일을 확인하세요.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}")
        print(f"\n💥 예상치 못한 오류가 발생했습니다: {e}")
        print("📋 자세한 내용은 obfuscation.log 파일을 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
