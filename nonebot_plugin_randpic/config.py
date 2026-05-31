import json
import re
from pathlib import Path
from pydantic import BaseModel, Extra
from typing import List, Optional
from nonebot import require
from nonebot import get_driver
from nonebot.log import logger

require("nonebot_plugin_localstore")

from nonebot_plugin_localstore import get_data_dir


class Config(BaseModel, extra='ignore'):
    randpic_store_dir_path: str = get_data_dir("nonebot_plugin_randpic")  # 用户自定义图片存储文件夹
    randpic_banner_group: List[int] = []  # 禁用群组列表
    randpic_endpoint: Optional[str] = None               # 建议填写自定义域名，尾部不用加/
    randpic_bucket: Optional[str] = None            # 存储空间名称
    randpic_region: Optional[str] = None               # Bucket所在地域
    randpic_oss_access_key_id: Optional[str] = None      # 阿里云用户AccessKey ID
    randpic_oss_access_key_secret: Optional[str] = None  # 阿里云用户AccessKey Secret
    randpic_oss_no_upload_list: List[str] = [] # 不上传oss的指令数组


COMMANDS_FILENAME = 'randpic_commands.json'
DEFAULT_COMMANDS: List[str] = ["capoo"]

# 名称合法字符集：仅允许字母、数字、汉字。SQL 表名、文件夹名都会按原样使用，
# 必须收紧字符集，否则会出现 SQL 注入 / 语法错 / 文件系统报错。
VALID_COMMAND_PATTERN = re.compile(r"^[A-Za-z0-9一-龥]+$")

# JSON 文件健康状态。文件不存在不算损坏（首次启动场景）；
# 解析失败或顶层不是 list 视为损坏，运行时禁止写回以保护管理员的原始内容。
commands_file_corrupted: bool = False


def is_commands_file_writable() -> bool:
    return not commands_file_corrupted


def commands_file_path(store_dir: str) -> Path:
    return Path(store_dir) / COMMANDS_FILENAME


def load_commands_file(store_dir: str) -> List[str]:
    """读取指令列表 JSON。
    - 文件不存在：写入默认列表并返回。
    - 解析失败 / 顶层非 list：置 corrupted 标记，返回空列表，运行时不再覆盖该文件。
    - 单条非法（非 str、空、含特殊字符）：跳过并告警。
    """
    global commands_file_corrupted
    path = commands_file_path(store_dir)
    if not path.exists():
        logger.info(f"未找到 {path}，使用默认指令列表 {DEFAULT_COMMANDS} 并写入文件")
        save_commands_file(store_dir, DEFAULT_COMMANDS)
        return list(DEFAULT_COMMANDS)
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        commands_file_corrupted = True
        logger.error(
            f"读取 {path} 失败（JSON 格式错误）：{e}；本次启动以空指令列表运行，"
            f"且运行时不会写回此文件以避免覆盖。请修复后重启 bot。"
        )
        return []
    if not isinstance(data, list):
        commands_file_corrupted = True
        logger.error(
            f"{path} 顶层必须是字符串数组，得到 {type(data).__name__}；本次启动以空指令列表运行，"
            f"且运行时不会写回此文件。"
        )
        return []
    result: List[str] = []
    for x in data:
        if not isinstance(x, str):
            logger.warning(f"{path} 中忽略非字符串条目: {x!r}")
            continue
        name = x.strip()
        if not name:
            logger.warning(f"{path} 中忽略空字符串条目")
            continue
        if not VALID_COMMAND_PATTERN.fullmatch(name):
            logger.warning(f"{path} 中忽略非法名称 {name!r}（仅允许字母、汉字、数字）")
            continue
        result.append(name)
    return list(dict.fromkeys(result))  # 去重，保留首次出现的顺序


def save_commands_file(store_dir: str, commands: List[str]) -> None:
    """全量覆盖写入指令列表 JSON。注意：调用方应先检查 is_commands_file_writable()。"""
    path = commands_file_path(store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(list(commands), f, ensure_ascii=False, indent=2)


config_dict = Config.model_validate(get_driver().config.dict())
randpic_store_dir_path: str = config_dict.randpic_store_dir_path
randpic_banner_group = config_dict.randpic_banner_group

# 指令列表唯一来源：randpic_commands.json
randpic_command_list: List[str] = load_commands_file(randpic_store_dir_path)

randpic_endpoint = config_dict.randpic_endpoint
randpic_bucket = config_dict.randpic_bucket
randpic_region = config_dict.randpic_region
randpic_oss_access_key_id = config_dict.randpic_oss_access_key_id
randpic_oss_access_key_secret = config_dict.randpic_oss_access_key_secret
randpic_oss_no_upload_list = config_dict.randpic_oss_no_upload_list
