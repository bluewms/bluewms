import hashlib
import json
import math
import re

from odoo.exceptions import AccessError, ValidationError

TOKEN = object()


def internal(records):
    return records.env.context.get('blue_barcode_token') is TOKEN


def protect(records):
    if not internal(records):
        raise AccessError(records.env._('请通过条码作业入口操作扫描记录.'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', value):
        raise ValidationError('Invalid barcode event/client identity.')
    return value


def quantity(value, zero=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or value > 1e9 or (not zero and value == 0)):
        raise ValidationError('Quantity must be finite and within the allowed range.')
    return value


def scan_text(value):
    if type(value) is not str or not value or len(value) > 8192 or '\x00' in value:
        raise ValidationError('Provide a barcode of 1 to 8192 characters.')
    return value
