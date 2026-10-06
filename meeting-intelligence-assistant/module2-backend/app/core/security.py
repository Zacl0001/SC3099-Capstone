# Authentication security functions:
#
# hash_password()
# verify_password()
# create_access_token()
# decode_token()

from pwdlib import PasswordHash
import hashlib #calcs token hash
import secrets #generates secure random vals

password_hasher = PasswordHash.recommended() #creates reusable object that handles verification n hashing

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    return password_hasher.verify(password, stored_hash)

def generate_session_token() -> str:
    return secrets.token_urlsafe(32) # generate 32 bytes and convert to url safe string

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest() #convert text to bytes then calcs a sha256 hash and returns as 64 chara string

