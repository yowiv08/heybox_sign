# 小黑盒签到脚本

## 环境要求

- nodejs
- 已准备好有效的 `heybox_ck`

## 快速开始

直接运行：

```bash
python heybox_sign.js
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
python heybox_sign.js
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

你可以把 `heybox_sign.js` 放进自己的仓库，或者直接放到青龙的脚本目录中。

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
