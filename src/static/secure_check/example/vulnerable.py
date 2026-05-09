import os
import sqlite3
import subprocess
import hashlib

# 1. Hardcoded Secret (Credential)
AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"  # 취약점: 하드코딩된 비밀키
AWS_SECRET_KEY = "1234567890abcdef1234567890abcdef12345678"

def login(username, password):
    # 2. SQL Injection
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # 취약점: 사용자 입력을 쿼리에 직접 포맷팅 (SQL Injection 위험)
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    cursor.execute(query) 
    return cursor.fetchone()

def ping_host(hostname):
    # 3. Command Injection
    # 취약점: 입력값을 검증 없이 쉘 명령어로 실행 (Command Injection 위험)
    command = f"ping -c 1 {hostname}"
    subprocess.call(command, shell=True)

def hash_password(password):
    # 4. Weak Hashing Algorithm
    # 취약점: MD5는 더 이상 안전하지 않은 해시 알고리즘임
    return hashlib.md5(password.encode()).hexdigest()

def read_user_file(filename):
    # 5. Path Traversal
    # 취약점: 파일 경로 검증 부재 (상위 디렉토리 접근 가능성)
    with open(filename, 'r') as f:
        return f.read()
