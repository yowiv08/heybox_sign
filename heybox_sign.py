"""
小黑盒签到脚本。

用法说明：
- `heybox_ck` 可直接填写从任意 `api.xiaoheihe.cn` 请求中复制的整段 Cookie
"""

import base64
import hashlib
import json
import os
import random
import re
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

BASE_URL = "https://api.xiaoheihe.cn"
TASK_LIST_PATH = "/task/list_v2/"
SIGN_PATH = "/task/sign_v3/sign"
STATE_PATH = "/task/sign_v3/get_sign_state"
HOOK_HKEY_PATH = "/hkey"

DEFAULT_UA = (
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/41.0.2272.118 Safari/537.36 ApiMaxJia/1.0"
)
DEFAULT_TIMEOUT = 15
DEFAULT_DEVICE_INFO = "HBP-AL00"
DEFAULT_HOOK_URL = "https://hkey.qcciii.com"
SIGN_STATE_OK = "ok"
SIGN_STATE_WAITING = "waiting"
TASK_STATE_FINISH = "finish"
STATE_POLL_DELAYS = (0, 2, 2, 3, 3, 5)


@dataclass
class ClientConfig:
    os_type: str
    x_os_type: str
    x_client_type: str
    hook_url: str
    os_version: str
    version: str
    build: str
    dw: str
    channel: str
    x_app: str
    time_zone: str
    referer: str
    user_agent: str
    timeout: int


@dataclass
class Account:
    cookie: str
    heybox_id: str
    imei: str
    device_info: str


@dataclass
class TaskSnapshot:
    nickname: str
    total_coin: Optional[str]
    sign_state: str
    sign_state_desc: str
    sign_streak: Optional[str]


@dataclass
class SignStateSnapshot:
    raw_status: str
    state: str
    msg: str
    reward_coin: Optional[str]
    sign_streak: Optional[str]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def display_text(value: Any) -> Optional[str]:
    text = normalize_text(value)
    return text or None


def parse_cookie_value(cookie: str, key: str) -> Optional[str]:
    for part in cookie.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        current_key, current_value = item.split("=", 1)
        if current_key.strip() == key:
            return current_value.strip()
    return None


def guess_heybox_id_from_cookie(cookie: str) -> Optional[str]:
    pkey = parse_cookie_value(cookie, "pkey")
    if not pkey:
        return None

    def extract_user_id(text: str) -> Optional[str]:
        match = re.search(r"_(\d{5,})", text)
        return match.group(1) if match else None

    direct = extract_user_id(pkey)
    if direct:
        return direct

    unquoted = urllib.parse.unquote(pkey)
    candidates = [unquoted]
    trimmed = unquoted.rstrip("_")
    if trimmed and trimmed != unquoted:
        candidates.append(trimmed)

    for candidate in candidates:
        hit = extract_user_id(candidate)
        if hit:
            return hit
        for pad_len in range(5):
            padded = candidate + ("=" * pad_len)
            try:
                raw = urllib.parse.unquote(padded).encode("utf-8")
                decoded = base64.urlsafe_b64decode(raw).decode("utf-8", errors="ignore")
            except Exception:
                continue
            hit = extract_user_id(decoded)
            if hit:
                return hit
    return None


def derive_imei(cookie: str) -> str:
    seed = parse_cookie_value(cookie, "pkey") or cookie
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]


def split_accounts(raw: str) -> List[str]:
    text = raw.replace("\r", "\n")
    parts = re.split(r"[&\n]+", text)
    return [item.strip() for item in parts if item.strip()]


def build_config_from_env() -> ClientConfig:
    return ClientConfig(
        os_type=os.getenv("XHH_OS_TYPE", "Android"),
        x_os_type=os.getenv("XHH_X_OS_TYPE", "Android"),
        x_client_type=os.getenv("XHH_X_CLIENT_TYPE", "mobile"),
        hook_url=DEFAULT_HOOK_URL,
        os_version=os.getenv("XHH_OS_VERSION", "12"),
        version="",
        build="",
        dw=os.getenv("XHH_DW", "360"),
        channel=os.getenv("XHH_CHANNEL", "heybox_xiaomi"),
        x_app=os.getenv("XHH_X_APP", "heybox"),
        time_zone=os.getenv("XHH_TIME_ZONE", "Asia/Shanghai"),
        referer=os.getenv("XHH_REFERER", "http://api.maxjia.com/"),
        user_agent=os.getenv("XHH_UA", DEFAULT_UA),
        timeout=int(os.getenv("XHH_TIMEOUT", str(DEFAULT_TIMEOUT))),
    )


def parse_accounts_from_env() -> List[Account]:
    raw_value = normalize_text(os.getenv("heybox_ck", ""))
    if not raw_value:
        raise RuntimeError("缺少环境变量: heybox_ck")

    account_rows = split_accounts(raw_value)
    default_device = os.getenv("XHH_DEVICE_INFO_DEFAULT", DEFAULT_DEVICE_INFO)
    accounts: List[Account] = []
    for index, row in enumerate(account_rows, start=1):
        cookie = row.strip()
        if not cookie:
            raise RuntimeError(f"账号{index}: cookie 不能为空")

        heybox_id = guess_heybox_id_from_cookie(cookie)
        if not heybox_id:
            raise RuntimeError(f"账号{index}: 无法解析 heybox_id")

        imei = derive_imei(cookie)
        device_info = default_device
        accounts.append(
            Account(
                cookie=cookie,
                heybox_id=str(heybox_id),
                imei=str(imei),
                device_info=str(device_info),
            )
        )
    return accounts


def rand_nonce(length: int = 32) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.SystemRandom().choice(chars) for _ in range(length))


def rand_rnd() -> str:
    hour = time.localtime().tm_hour
    return f"{hour}:{random.getrandbits(32):X}"


def build_hook_url(config: ClientConfig, path: str, params: Optional[Dict[str, str]] = None) -> str:
    route = path if path.startswith("/") else f"/{path}"
    url = f"{config.hook_url}{route}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return url


def fetch_hook_json(config: ClientConfig, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    url = build_hook_url(config, path, params)
    request = urllib.request.Request(
        url=url,
        headers={"User-Agent": config.user_agent},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP错误 {exc.code} {path}: {body}") from exc
    except Exception as exc:
        raise RuntimeError(f"请求失败 {path}: {exc}") from exc

    try:
        return json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"JSON解析失败 {path}: {body[:300]}") from exc


def fetch_hook_result(config: ClientConfig, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    payload = fetch_hook_json(config, path, params)
    if normalize_text(payload.get("status")) != SIGN_STATE_OK:
        status = normalize_text(payload.get("status")) or "unknown"
        msg = normalize_text(payload.get("msg")) or "无"
        raise RuntimeError(f"status={status} msg={msg}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("返回结果缺少 result")
    return result


def fetch_hkey_value(path: str, timestamp: str, account: Account, config: ClientConfig) -> str:
    hook_data = fetch_hook_result(
        config,
        HOOK_HKEY_PATH,
        {
            "path": path,
            "time": timestamp,
            "imei": account.imei,
            "heybox_id": account.heybox_id,
        },
    )
    hkey = normalize_text(hook_data.get("hkey"))
    if not hkey:
        raise RuntimeError("未返回 hkey")

    latest_version = normalize_text(hook_data.get("version"))
    latest_build = normalize_text(hook_data.get("build"))
    if not latest_version:
        raise RuntimeError("未返回 version")
    if not latest_build or not latest_build.isdigit():
        raise RuntimeError("未返回有效 build")
    config.version = latest_version
    config.build = latest_build
    return hkey


def print_current_client_version(account: Account, config: ClientConfig) -> None:
    fetch_hkey_value(TASK_LIST_PATH, str(int(time.time())), account, config)
    print(f"当前版本：{config.version} build={config.build}")


def build_params(path: str, account: Account, config: ClientConfig) -> Dict[str, str]:
    current_time = str(int(time.time()))
    hkey = fetch_hkey_value(path, current_time, account, config)
    return {
        "heybox_id": account.heybox_id,
        "imei": account.imei,
        "device_info": account.device_info,
        "nonce": rand_nonce(),
        "hkey": hkey,
        "_rnd": rand_rnd(),
        "os_type": config.os_type,
        "x_os_type": config.x_os_type,
        "x_client_type": config.x_client_type,
        "os_version": config.os_version,
        "version": config.version,
        "build": config.build,
        "_time": current_time,
        "dw": config.dw,
        "channel": config.channel,
        "x_app": config.x_app,
        "time_zone": config.time_zone,
    }


def http_get_json(path: str, account: Account, config: ClientConfig) -> Dict[str, Any]:
    params = build_params(path, account, config)
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": config.user_agent,
        "Referer": config.referer,
        "Cookie": account.cookie,
    }

    request = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP错误 {exc.code} {path}: {body}") from exc
    except Exception as exc:
        raise RuntimeError(f"请求失败 {path}: {exc}") from exc

    try:
        return json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"JSON解析失败 {path}: {body[:300]}") from exc


def format_json_line(data: Dict[str, Any]) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(data)


def request_with_retry(path: str, account: Account, config: ClientConfig, retries: int = 1) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for _ in range(retries + 1):
        try:
            return http_get_json(path, account, config)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(str(last_error) if last_error else f"请求失败: {path}")


def find_sign_task(result: Dict[str, Any]) -> Dict[str, Any]:
    task_groups = result.get("task_list")
    if not isinstance(task_groups, list):
        return {}
    for group in task_groups:
        if not isinstance(group, dict):
            continue
        tasks = group.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            if normalize_text(task.get("type")) == "sign" or normalize_text(task.get("title")) == "签到":
                return task
    return {}


def parse_task_snapshot(response: Dict[str, Any]) -> TaskSnapshot:
    result = response.get("result")
    if not isinstance(result, dict):
        result = {}
    user = result.get("user")
    if not isinstance(user, dict):
        user = {}
    level_info = user.get("level_info")
    if not isinstance(level_info, dict):
        level_info = {}
    sign_task = find_sign_task(result)
    return TaskSnapshot(
        nickname=normalize_text(user.get("username")),
        total_coin=display_text(level_info.get("coin")),
        sign_state=normalize_text(sign_task.get("state")),
        sign_state_desc=normalize_text(sign_task.get("state_desc")),
        sign_streak=display_text(sign_task.get("sign_in_streak")),
    )


def parse_sign_state(response: Dict[str, Any]) -> SignStateSnapshot:
    result = response.get("result")
    if not isinstance(result, dict):
        result = {}
    return SignStateSnapshot(
        raw_status=normalize_text(response.get("status")),
        state=normalize_text(result.get("state")),
        msg=normalize_text(response.get("msg")),
        reward_coin=display_text(result.get("sign_in_coin")),
        sign_streak=display_text(result.get("sign_in_streak")),
    )


def poll_sign_state(account: Account, config: ClientConfig) -> SignStateSnapshot:
    latest = SignStateSnapshot(raw_status="", state="", msg="", reward_coin=None, sign_streak=None)
    for delay in STATE_POLL_DELAYS:
        if delay:
            time.sleep(delay)
        response = request_with_retry(STATE_PATH, account, config, retries=1)
        latest = parse_sign_state(response)
        if latest.raw_status != SIGN_STATE_OK:
            return latest
        if latest.state != SIGN_STATE_WAITING:
            return latest
    return latest


def print_account_header(index: int, account: Account, snapshot: TaskSnapshot) -> None:
    print(f"\n========== 账号{index} ==========")
    label = snapshot.nickname or account.heybox_id
    print(f"账号={label} 黑盒ID={account.heybox_id} IMEI={account.imei} 设备={account.device_info}")


def print_coin_summary(result_text: str, reward_coin: Optional[str], total_coin: Optional[str], streak: Optional[str]) -> None:
    print(f"签到结果: {result_text}")
    print(f"本次获得H币: {reward_coin or '0'}")
    print(f"当前总H币: {total_coin or '未知'}")
    if streak:
        print(f"连续签到: {streak}天")


def run_account(index: int, account: Account, config: ClientConfig) -> bool:
    task_before = request_with_retry(TASK_LIST_PATH, account, config, retries=1)
    snapshot_before = parse_task_snapshot(task_before)
    print_account_header(index, account, snapshot_before)

    if snapshot_before.sign_state == TASK_STATE_FINISH:
        print_coin_summary("今日已签到", "0", snapshot_before.total_coin, snapshot_before.sign_streak)
        if snapshot_before.sign_state_desc:
            print(f"状态说明: {snapshot_before.sign_state_desc}")
        return True

    sign_response = request_with_retry(SIGN_PATH, account, config, retries=1)
    sign_state = poll_sign_state(account, config)
    task_after = request_with_retry(TASK_LIST_PATH, account, config, retries=1)
    snapshot_after = parse_task_snapshot(task_after)
    total_coin = snapshot_after.total_coin or snapshot_before.total_coin
    streak = sign_state.sign_streak or snapshot_after.sign_streak or snapshot_before.sign_streak

    if sign_state.raw_status == SIGN_STATE_OK and sign_state.state == SIGN_STATE_OK:
        print_coin_summary("成功", sign_state.reward_coin, total_coin, streak)
        if sign_state.msg:
            print(f"接口提示: {sign_state.msg}")
        return True

    if snapshot_after.sign_state == TASK_STATE_FINISH:
        print_coin_summary("今日已签到", "0", total_coin, streak)
        failure_hint = sign_state.msg or normalize_text(sign_response.get("msg"))
        if failure_hint:
            print(f"接口提示: {failure_hint}")
        return True

    error_message = (
        sign_state.msg
        or normalize_text(sign_response.get("msg"))
        or sign_state.state
        or normalize_text(sign_response.get("status"))
        or "未知错误"
    )
    print("签到结果: 失败")
    print(f"失败信息: {error_message}")
    print(f"当前总H币: {total_coin or '未知'}")
    return False


def main() -> int:
    try:
        config = build_config_from_env()
        accounts = parse_accounts_from_env()
        print_current_client_version(accounts[0], config)
    except Exception as exc:
        print(f"初始化失败：{exc}")
        
        print("示例: heybox_ck='pkey=xxx; x_xhh_tokenid=xxx;'")
        return 1

    success_count = 0
    for index, account in enumerate(accounts, start=1):
        try:
            if run_account(index, account, config):
                success_count += 1
        except Exception as exc:
            print(f"\n========== 账号{index} ==========")
            print(f"签到结果: 失败")
            print(f"失败信息: {exc}")

    total_accounts = len(accounts)
    print(f"\n完成: {success_count}/{total_accounts}")
    return 0 if success_count == total_accounts else 1


if __name__ == "__main__":
    sys.exit(main())
