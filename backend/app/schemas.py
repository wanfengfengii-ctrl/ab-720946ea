"""Pydantic-neutral schemas.

请求体采用手工校验（见 :mod:`app.validation`），这里只定义响应中复用的数据结构与
常量，保证所有错误信息都能携带精确定位（loc）。
"""

MIN_MODES = 3
MAX_MODES = 12
MIN_SENTINELS = 4
MAX_SENTINELS = 18
