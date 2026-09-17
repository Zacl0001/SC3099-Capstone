# Authentication security functions:
#
# hash_password()
# verify_password()
# create_access_token()
# decode_token()

from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended() #creates reusable object that handles verification n hashing

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    return password_hasher.verify(password, stored_hash)