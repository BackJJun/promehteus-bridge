from typing import Optional, List, Dict
from urllib.parse import quote

import asyncpg
from asyncpg import Pool
from loguru import logger

import config

DATABASE_URL = config.DATABASE_POSTGRESQL_URL
DATABASE_PORT = config.DATABASE_POSTGRESQL_PORT
DATABASE_DBNAME = config.DATABASE_POSTGRESQL_DBNAME
DATABASE_USERNAME = config.DATABASE_POSTGRESQL_USERNAME
DATABASE_PASSWORD = config.DATABASE_POSTGRESQL_PASSWORD

# 특수 문자가 포함된 비밀번호를 URL-인코딩
ENCODED_DATABASE_PASSWORD = quote(DATABASE_PASSWORD)

DATABASE_DSN = f"postgresql://{DATABASE_USERNAME}:{ENCODED_DATABASE_PASSWORD}@{DATABASE_URL}:{DATABASE_PORT}/{DATABASE_DBNAME}"


class Connection:
    connection_pool: Optional[Pool] = None  # Initialize as None

    """
    fetch	여러 행 조회	Record 리스트	여러 사용자의 데이터를 가져올 때
    fetchrow	단일 행 조회	Record 객체	특정 ID의 사용자 정보 조회
    fetchval	단일 값 조회	단일 값	집계 값, 특정 열의 값 조회
    fetchmany	일정 개수의 행 조회	Record 리스트	페이징된 데이터 가져오기
    execute	데이터 변경 작업	성공한 행 수 포함 문자열	INSERT, UPDATE, DELETE 작업
    executemany	동일한 쿼리를 여러 번 실행	None	여러 행을 한 번에 INSERT
    """

    @classmethod
    async def create_pool(cls):
        """런 서버 후 커넥션 풀을 생성 한다"""
        # Pool이 None이거나 이미 닫혀있는 경우 새로 생성
        if cls.connection_pool is None or cls.connection_pool._closed:
            logger.info("커넥션 생성 시작")
            cls.connection_pool = await asyncpg.create_pool(DATABASE_DSN, min_size=3, max_size=10)
            logger.info("커넥션 생성 완료")

    @staticmethod
    async def execute(sql, args: tuple, result_ignore=False):
        """단순 insert, update, delete시 커밋은 결과가 1개라도 있을떄 알아서 됨"""
        connection = await Connection.connection_pool.acquire()
        try:
            await connection.execute("BEGIN")

            # 연결을 사용하여 작업을 처리
            result = await connection.execute(sql, *args)

        except Exception as e:
            logger.info("익샙션 발생 => 롤백")
            await connection.execute("ROLLBACK")
            raise e
        else:
            row_count = int(result.split()[-1])
            if row_count or result_ignore:
                # logger.info("결과 성공 => 커밋")
                await connection.execute("COMMIT")
                return True
            else:
                logger.info("결과 실패 => 롤백")
                await connection.execute("ROLLBACK")
                return False
        finally:
            await Connection.connection_pool.release(connection)

    @staticmethod
    async def execute_many(sql, args: List[tuple]):
        """insert many시 사용"""
        pass

    @staticmethod
    async def execute_list(data_list: List[Dict], ignore_idx):
        """여러 insert update delete를 수행하고  ignore_idx에 나와 있는 쿼리는 결과가 0이라도 commit한다
            data_list = [{sql: str, args: tuple]
        """
        pass

    @staticmethod
    async def execute_one(sql, args=tuple()):
        """단일 행 리턴"""
        connection = await Connection.connection_pool.acquire()
        try:
            result = await connection.fetchrow(sql, *args)
            return dict(result) if result else None
        finally:
            await Connection.connection_pool.release(connection)

    @staticmethod
    async def execute_one_val(sql, args: tuple = tuple()):
        """단일 값 리턴"""
        connection = await Connection.connection_pool.acquire()
        try:
            value = await connection.fetchval(sql, *args)
            return value
        finally:
            await Connection.connection_pool.release(connection)

    @staticmethod
    async def execute_all(sql, args=tuple()):
        """여러 행 리턴"""
        connection = await Connection.connection_pool.acquire()
        try:
            rows = await connection.fetch(sql, *args)
            return [dict(row) for row in rows] if rows else []
        finally:
            await Connection.connection_pool.release(connection)

    @staticmethod
    async def execute_transaction(callback):
        """콜백 함수를 트랜잭션 내에서 실행, 쿼리 여러개를 하나의 트랜잭션에서 실행할때"""
        connection = await Connection.connection_pool.acquire()
        # logger.info("트랜잭션을 시작 합니다 (쿼리 여러개 실행~!)")
        try:
            await connection.execute("BEGIN")
            result = await callback(connection)
            await connection.execute("COMMIT")
            # logger.info("트랜잭션 커밋 완료")
            return result
        except Exception as e:
            await connection.execute("ROLLBACK")
            logger.info("트랜잭션 롤백 완료")
            raise e
        finally:
            await Connection.connection_pool.release(connection)
