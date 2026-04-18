# 小黑盒签到脚本

## 环境要求

- Python 3
- 已准备好有效的 `heybox_ck`

## 快速开始

直接运行：

```bash
python heybox_sign.py
```

脚本启动后会先输出当前版本，例如：

```text
当前版本：1.3.382 build=1075
```

然后再按账号顺序执行签到。

## 本地运行

### 单账号

直接填写从任意 `api.xiaoheihe.cn` 请求中复制出来的**整段 Cookie**。

示例：

```bash
heybox_ck='pkey=xxx; x_xhh_tokenid=xxx;'
python heybox_sign.py
```

### 多账号

本地命令行场景下，推荐一行一个账号。

示例：

```text
pkey=aaa; x_xhh_tokenid=aaa;
pkey=bbb; x_xhh_tokenid=bbb;
```

## 青龙面板

### 1. 准备脚本

你可以把 `heybox_sign.py` 放进自己的仓库，或者直接放到青龙的脚本目录中。

### 2. 新建环境变量

在青龙面板环境变量中新增：

- 名称：`heybox_ck`

单账号时，新建 1 个 `heybox_ck` 即可，值直接填整段 Cookie。

多账号时，直接新建多个同名 `heybox_ck` 环境变量即可，每个变量填 1 个账号的整段 Cookie。

示例：

```text
heybox_ck = pkey=aaa; x_xhh_tokenid=aaa;
heybox_ck = pkey=bbb; x_xhh_tokenid=bbb;
heybox_ck = pkey=ccc; x_xhh_tokenid=ccc;
```

### 3. 定时规则

定时规则可以自行设置，常见示例：

```text
5 9 * * *
```

表示每天 9:05 执行一次。


## 接口说明

脚本内部依赖：

```text
GET https://hkey.qcciii.com/hkey
```

请求参数：

1. `path`：小黑盒接口路径，例如 `/task/sign_v3/sign`
2. `time`：Unix 秒级时间戳
3. `imei`：设备标识
4. `heybox_id`：用户 ID

返回字段：

1. `result.hkey`
2. `result.version`
3. `result.build`
4. `result.updated_at`

这个接口如果不可用，签到脚本会直接失败。

## 运行输出示例

```text
当前版本：1.3.382 build=1075

========== 账号1 ==========
账号=xxx 黑盒ID=xxx IMEI=cfdae588b08808cf 设备=HBP-AL00
签到结果: 成功
本次获得H币: 5
当前总H币: 123
连续签到: 7天

完成: 1/1
```

## 说明

当前项目主要聚焦签到流程，欢迎开发者在此基础上继续补充和完善其他任务接口。
