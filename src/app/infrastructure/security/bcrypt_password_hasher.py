"""bcrypt implementation of `app.domain.ports.password_hasher.PasswordHasher`."""

import bcrypt


class BcryptPasswordHasher:
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            # bcrypt<5 silently used the first 72 bytes; bcrypt>=5 raises instead.
            # Truncate so hashes of longer passwords made by bcrypt<5 still verify.
            return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
        except ValueError:
            # Malformed stored hash - treat as "does not match".
            return False
