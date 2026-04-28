# -*- coding: utf-8 -*-
"""
Модуль для шифрования/дешифрования конфигурации
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_key_from_password(password: str, salt: bytes = None) -> bytes:
    """Генерирует ключ шифрования из пароля"""
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

def encrypt_data(data: str, password: str) -> tuple:
    """Шифрует данные"""
    key, salt = generate_key_from_password(password)
    f = Fernet(key)
    encrypted_data = f.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted_data).decode(), base64.urlsafe_b64encode(salt).decode()

def decrypt_data(encrypted_data: str, password: str, salt: str) -> str:
    """Дешифрует данные"""
    salt_bytes = base64.urlsafe_b64decode(salt.encode())
    key, _ = generate_key_from_password(password, salt_bytes)
    f = Fernet(key)
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
    decrypted_data = f.decrypt(encrypted_bytes)
    return decrypted_data.decode()