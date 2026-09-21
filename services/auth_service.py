from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash


class AuthService:

    @staticmethod
    def hash_password(password):

        return generate_password_hash(
            password,
            method="pbkdf2:sha256",
            salt_length=16
        )

    @staticmethod
    def verificar(password, password_hash):

        return check_password_hash(
            password_hash,
            password
        )