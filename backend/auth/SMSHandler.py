import random
import string

codes: dict[str, str] = dict()


def set_code(phone: str):
    if phone in codes:
        raise Exception("Code already requested")

    code = ''.join(random.choices(string.digits, k=6))

    codes[phone] = code


def verify_code(phone: str, code: str) -> bool:
    if phone not in codes:
        raise Exception("Code hasn't been requested yet")

    result = codes[phone] == code

    if result:
        codes.pop(phone, "")

    return result
