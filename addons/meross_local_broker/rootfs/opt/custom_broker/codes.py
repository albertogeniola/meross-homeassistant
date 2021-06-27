from enum import Enum


class ExtendedErrorCodes(Enum):

    CODE_NO_ERROR = 0
    """Not an error"""

    CODE_MISSING_PASSWORD = 1001
    """Wrong or missing password"""

    CODE_UNEXISTING_ACCOUNT = 1002
    """Account does not exist"""

    CODE_DISABLED_OR_DELETED_ACCOUNT = 1003
    """This account has been disabled or deleted"""

    CODE_WRONG_CREDENTIALS = 1004
    """Wrong email or password"""

    CODE_INVALID_EMAIL = 1005
    """Invalid email address"""

    CODE_BAD_PASSWORD_FORMAT = 1006
    """Bad password format"""

    CODE_WRONG_EMAIL = 1008
    """This email is not registered"""

    CODE_TOKEN_INVALID = 1019
    """Token expired"""

    CODE_TOKEN_EXPIRED = 1200
    """Token has expired"""

    CODE_TOKEN_ERROR = 1022
    """Token error"""

    CODE_TOO_MANY_TOKENS = 1301
    """Too many tokens have been issued"""

    CODE_GENERIC_ERROR = 5000
    """Unknown or generic error"""
