# CSCI 587 Lab 1 完成步骤指南

> **作业名称**：Lab 1: Packet Sniffing for Reconnaissance
> **提交截止日期**：9/14
> **实验平台**：SEED Ubuntu 20.04 VM + Docker 容器
> **本指南用法**：按章节顺序从上往下做，每一步都给出了要敲的命令、预期看到的结果、以及需要截图的地方（标注 📸）。

---

## 0. 作业总览

### 0.1 作业要做什么

本次作业分两大部分、共 4 个任务，全部在你自己的 SEED 虚拟机里完成：

| 任务     | 内容                                                 | 性质            |
| -------- | ---------------------------------------------------- | --------------- |
| Task 1.1 | 用 Scapy 写嗅探器（sniffer），并设置 3 种 BPF 过滤器 | 命令 + 少量代码 |
| Task 1.2 | 用 Scapy 伪造源 IP 的 ICMP echo request 包           | 交互式命令      |
| Task 1.3 | 自己实现 traceroute（靠改 TTL 字段）                 | 代码或手动操作  |
| Task 1.4 | 嗅探 + 伪造结合：让 ping 永远"成功"                  | 完整程序        |

### 0.2 提交要求（第 4 节原文要求）

你需要提交一份**详细的实验报告（lab report）**，必须包含：

1. **截图**：证明你确实做了每个任务；
2. **观察记录**：你看到了什么；
3. **解释**：对"有趣或令人意外"的现象给出解释（尤其是 Task 1.1B 权限对比、Task 1.4 三个 ping 的差异）；
4. **重要代码片段 + 逐段解释**：只贴代码不写解释 = 不给分。

### 0.3 实验伦理提醒（报告开头可引用）

所有操作只允许在本实验自带的隔离 Docker 网络 `10.9.0.0/24` 内进行。同样的命令指向未经许可的网络属于非法拦截。

### 0.4 实验拓扑

```
            Network: 10.9.0.0/24
  ┌──────────────────┬──────────────────┬──────────────────┐
  │   Attacker       │     Host A       │     Host B       │
  │   10.9.0.1       │   10.9.0.5       │   10.9.0.6       │
  │  (host 模式)      │  (普通容器)       │  (普通容器)       │
  └──────────────────┴──────────────────┴──────────────────┘
```

- **Attacker 容器**：跑你的攻击/嗅探代码，使用 `network_mode: host`，因此能看到 VM 网卡上的全部流量；
- **Host A / Host B**：普通容器，用来生成流量（ping 等）；
- 你的 VM 自己的 IP 是 `10.9.0.1`。

---

## 1. 环境搭建（从零开始）

### 1.1 下载并安装 SEED Ubuntu 20.04 VM

1. 在浏览器打开 SEED 实验下载页：
   ```
   https://seedsecuritylabs.org/labsetup.html
   ```
2. 找到 **"Ubuntu 20.04 VM"** 的预编译镜像（约 2~3 GB），下载解压。
   - 如果你拿到的是 **`.ova`**：直接用"导入虚拟电脑"方式（见 1.1.3）；
   - 如果你拿到的是 **`.vdi`**（VirtualBox 虚拟硬盘文件，只是一个磁盘，不是完整虚拟机）：按下面 **1.1.1 / 1.1.2** 新建虚拟机再挂载它。
3. 安装虚拟机软件（二选一）：
   - **VirtualBox**：https://www.virtualbox.org/wiki/Downloads （建议同时装 Extension Pack）
   - **VMware Workstation Pro（Windows/Linux）/ Fusion（macOS）**

#### 1.1.1 情况 A：用 VirtualBox 打开 .vdi（推荐，.vdi 是 VirtualBox 原生格式）

1. 打开 **Oracle VM VirtualBox Manager**，点击工具栏 **新建（New）**；
2. **名称与操作系统**：

   - Name：`SEEDUbuntu20.04`（随便起）
   - Type：`Linux`
   - Version：`Ubuntu (64-bit)`
   - > 如果下拉框里只有 32-bit，说明 BIOS/UEFI 里没开 CPU 虚拟化（VT-x/AMD-V），重启电脑进 BIOS 打开后再试；
     >
   - 点 **下一步（Next）**；
3. **内存大小**：建议 **2048 MB 以上**（4096 MB 更流畅）→ 下一步；
4. **硬盘**：选择 **使用现有虚拟硬盘文件（Use an existing virtual hard disk file）** → 点文件夹图标 → **添加（Add）** → 浏览到你下载的 `.vdi` 文件 → 选中 → **创建（Create）**；

   - 此时虚拟机已建好，但还没开机，先做第 5 步设置；
5. **开机前必做的设置**（选中虚拟机 → 点 **设置 Settings**）：

   - **系统（System）→ 主板（Motherboard）**：启动顺序里勾上 `Hard Disk`；固件默认 BIOS 即可；
   - **系统 → 处理器（Processor）**：拖到 **2 CPU**；
   - **网络（Network）→ 网卡 1（Adapter 1）**：勾选 **启用网络连接**，连接方式选：
     - **网络地址转换(NAT)**：默认即可，VM 能上网（下载 Labsetup.zip 用）；本实验的容器实验全在 VM 内部的 `10.9.0.0/24`，不依赖外部网络模式；
     - 或 **桥接网卡（Bridged Adapter）**：想让宿主机直接访问 VM 时用；
   - **显示（Display）→ 屏幕**：显存拉到 128 MB（可选，防止桌面花屏）；
6. 点 **启动（Start）**，等待开机，登录账户：

   - `root`（密码：`seed`）
   - `seed`（普通用户，密码：`seed`）

   > 记住：**所有攻击代码都要用 root 运行**，因为嗅探和发包需要特权。
   >
7. **强烈建议**：开机正常后立刻打快照 —— 菜单 **机器（Machine）→ 快照（Take Snapshot）**，命名 `clean`。实验环境搞坏了一键还原。

#### 1.1.2 情况 B：用 VMware 打开 .vdi（VMware 不认 .vdi，必须先转换成 .vmdk）

**第一步：转换磁盘格式**（在宿主机上执行，装没装 VirtualBox 都行）

方法 ①：用 VirtualBox 自带的 `VBoxManage`（装了 VirtualBox 就有）：

- Windows（CMD/PowerShell）：
  ```bat
  "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" clonemedium disk "C:\路径\seed.vdi" "C:\路径\seed.vmdk" --format VMDK
  ```
- Linux/macOS：
  ```bash
  VBoxManage clonemedium disk ~/下载/seed.vdi ~/下载/seed.vmdk --format VMDK
  ```

方法 ②：用 qemu（没装 VirtualBox 时）：

- Windows/Linux：
  ```bash
  qemu-img convert -f vdi -O vmdk seed.vdi seed.vmdk
  ```

  （qemu 在 Ubuntu 上：`sudo apt install qemu-utils`；Windows 可从 https://qemu.weilnetz.de/w64/ 下载）

**第二步：在 VMware 中新建虚拟机并挂载 .vmdk**

1. 打开 VMware Workstation，菜单 **文件（File）→ 新建虚拟机（New Virtual Machine）**；
2. 选 **典型（Typical）** → 下一步；
3. 安装来源：选 **稍后安装操作系统（I will install the operating system later）** → 下一步；
4. 客户机操作系统：**Linux**，版本：**Ubuntu 64-bit** → 下一步；
5. 虚拟机名称/位置：默认或自选 → 下一步；
6. 磁盘：选 **使用现有虚拟磁盘（Use an existing virtual disk）** → **浏览** → 选中刚才转换出的 `seed.vmdk` → 下一步；
   - 如果弹出"选择现有磁盘格式"，选 **Convert the existing virtual disk to a newer format** 或保持默认均可；
7. 点 **完成（Finish）**；
8. **开机前设置**：选中虚拟机 → **编辑虚拟机设置（Edit virtual machine settings）**：
   - **内存**：≥ 2048 MB；
   - **处理器**：2 个；
   - **网络适配器**：**NAT**（默认即可）；
   - **硬盘（Hard Disk）**：如果启动时报磁盘/控制器错误，把 **磁盘类型** 在 `SCSI` / `SATA` / `IDE` 之间切换重试（SCSI 不行就换 SATA）；
9. **开启此虚拟机**，登录 `root` / `seed`（密码均为 `seed`）；
10. 同样建议：`虚拟机 → 快照 → 拍摄快照` 存一个干净状态。

> **报错速查**：
>
> | 现象                                  | 处理                                                                                        |
> | ------------------------------------- | ------------------------------------------------------------------------------------------- |
> | VMware 提示磁盘无效/无法打开          | 重新用`qemu-img convert` 转一次，或转成 `vmdk`（streamOptimized 之外的子格式）          |
> | 开机黑屏/找不到系统                   | 编辑虚拟机设置 → 硬盘 → 尝试改控制器类型（SCSI↔SATA↔IDE）；确认 BIOS 里启动顺序先从硬盘 |
> | VirtualBox 新建时没有 64-bit 选项     | 进 BIOS 开启`Intel VT-x` / `AMD-V` / `SVM`                                            |
> | VirtualBox 启动报`VT-x is disabled` | 同上，或在虚拟机设置里去掉"嵌套虚拟化"相关项                                                |

#### 1.1.3 情况 C：拿到的是 .ova（最省事）

- **VirtualBox**：`文件（File）→ 导入虚拟电脑（Import Appliance）→ 选择 .ova → 下一步 → 完成`
- **VMware**：`文件（File）→ 打开（Open）→ 选择 .ova`（自动转换为 vmdk 虚拟机）

#### 1.1.4 登录与账户

启动 VM 并登录。SEED VM 默认提供两个账户：

- `root`（密码：`seed`）
- `seed`（普通用户，密码：`seed`）

> 记住：**所有攻击代码都要用 root 运行**，因为嗅探和发包需要特权。

📸 **截图 1**：VM 成功启动、登录到桌面的界面。

### 1.2 在 VM 内下载 Labsetup.zip

1. 打开 VM 里的 Firefox 浏览器，进入本实验页面（课程提供的 Lab 1 页面），下载 **Labsetup.zip**。

   - 如果课程页面下载不便，也可以在宿主机下载后拖进 VM（VirtualBox 可直接拖拽，或用 `Devices → Insert Guest Additions` 后共享文件夹）。
2. 打开 VM 的终端（Terminal），解压：

   ```bash
   unzip ~/Downloads/Labsetup.zip -d ~/
   cd ~/Labsetup
   ls -l
   ```

   你应该能看到类似文件：
   ```
   docker-compose.yml
   volumes/
   （可能还有 Dockerfile 等）
   ```
3. 查看 compose 文件，确认攻击者容器用了 host 模式和共享目录：

   ```bash
   cat docker-compose.yml
   ```

   重点找这两行配置（出现在 attacker 容器那一段）：
   ```yaml
   volumes:
      - ./volumes:/volumes
   network_mode: host
   ```

📸 **截图 2**：`ls` 显示 Labsetup 目录内容 + `docker-compose.yml` 关键配置。

### 1.3 构建并启动容器

SEED VM 已经预装了 docker-compose，并配置好了别名。在 `~/Labsetup` 目录下执行：

```bash
# 构建镜像（第一次必须做，耗时几分钟）
dcbuild
# 等价于 docker-compose build

# 启动所有容器（后台运行）
dcup
# 等价于 docker-compose up

# 以后要关闭环境时：
# dcdown    等价于 docker-compose down
```

如果 `dcbuild`/`dcup` 别名不存在（比如你用了非 SEED 的 Ubuntu），直接用原生命令：

```bash
sudo docker-compose build
sudo docker-compose up -d
```

验证容器都在运行：

```bash
dockps
# 等价于 docker ps --format "{{.ID}} {{.Names}}"
```

预期输出类似：

```
b1004832e275 hostA-10.9.0.5
0af4ea7a3e2e hostB-10.9.0.6
9652715c8e0a hostC-10.9.0.7
```

> 注意：Labsetup 里的容器名字可能与上例不同（比如 attacker 容器），以你实际 `dockps` 输出为准。

📸 **截图 3**：`dockps` 输出，显示所有容器已启动。

### 1.4 进入容器验证

```bash
# 前几位字符能唯一标识容器即可，不必打全 ID
docksh 96
# 等价于 docker exec -it 9652715c8e0a /bin/bash
```

进去后确认网络：

```bash
ip addr
ping -c 2 10.9.0.1      # 从容器 ping 你的 VM
ping -c 2 10.9.0.5      # 容器之间互 ping
```

看到 `64 bytes from ...` 即为连通。按 `Ctrl+D` 或输入 `exit` 退出容器 shell。

📸 **截图 4**：容器内 `ping 10.9.0.1` 成功的输出。

### 1.5 获取网络接口名（关键！后面所有程序都要用）

**方法一：用 ifconfig 找 10.9.0.1**

```bash
ifconfig
```

在输出里找 `inet 10.9.0.1` 那个接口，它的名字就是 `br-` + Docker 网络 ID 后 12 位，例如：

```
br-c93733e9f913: flags=4163<UP,BROADCAST,RUNNING,MULTICAST> mtu 1500
        inet 10.9.0.1 netmask 255.255.255.0 broadcast 10.9.0.255
```

那么你的接口名就是 **`br-c93733e9f913`**。

**方法二：用 docker network 命令**

```bash
docker network ls
```

输出：

```
NETWORK ID          NAME                                 DRIVER   SCOPE
a82477ae4e6b        bridge                               bridge   local
e99b370eb525        host                                 host     local
df62c6635eae        none                                 null     local
c93733e9f913        seed-net                             bridge   local
```

找到 `seed-net` 那行的 NETWORK ID（`c93733e9f913`），接口名就是 `br-c93733e9f913`。

> ⚠️ **重要**：你机器上的 ID 大概率和示例**不一样**，以后粘贴代码时要替换成你自己的接口名。

📸 **截图 5**：`ifconfig` 显示 `br-xxx` 接口持有 10.9.0.1。

### 1.6 理解共享目录（写代码的地方）

攻击者容器通过 Docker volumes 挂载了共享目录：

```
VM 上的  ~/Labsetup/volumes   ←→   容器内的 /volumes
```

**操作约定**：用你喜欢的编辑器（gedit/vim/nano）在 **VM 的 `~/Labsetup/volumes/`** 里写 `.py` 文件，这些文件会自动出现在容器里；或者直接在宿主机（VM）上以 root 运行（本实验多数任务允许在 VM 上运行，因为 VM 自己就是 10.9.0.1）。

```bash
mkdir -p ~/Labsetup/volumes
cd ~/Labsetup/volumes
```

### 1.7 确认 Scapy 已安装

```bash
python3 -c "import scapy; print(scapy.__version__)"
```

如果提示 `ModuleNotFoundError`：

```bash
sudo apt update
sudo apt install -y python3-scapy tcpdump wireshark
```

> 安装 wireshark 时如果弹出 "Should non-superusers be able to capture packets?" 选 **Yes**（或把 `seed` 用户加入 `wireshark` 组：`sudo usermod -aG wireshark seed`，然后**重新登录**生效）。

测试 Scapy 可用（需要 root）：

```bash
sudo python3 -c "from scapy.all import *; a = IP(); a.show()"
```

预期输出：

```
###[ IP ]###
  version   = 4
  ihl       = None
  tos       = 0x0
  len       = None
  ...
```

📸 **截图 6**：Scapy 测试成功输出。

### 1.8 常见问题排查

| 现象                                                    | 解决办法                                                                         |
| ------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `dcbuild: command not found`                          | 用`docker-compose build`，或 `alias dcbuild='docker-compose build'`          |
| `permission denied while trying to connect to docker` | 加`sudo`，或 `sudo usermod -aG docker $USER` 后重新登录                      |
| `docker-compose: command not found`                   | `sudo apt install docker-compose`                                              |
| 容器起来后没有 10.9.0.1                                 | `docker-compose down` 后重新 `dcup`，确认 compose 文件里有 `seed-net` 网络 |
| 构建报错拉不到镜像                                      | 检查 VM 能否上网：`ping -c 2 8.8.8.8`；必要时配置代理                          |

---

## 2. Task 1.1：用 Scapy 嗅探数据包

### 2.1 编写 sniffer.py

在 VM 上创建文件：

```bash
cd ~/Labsetup/volumes
gedit sniffer.py &        # 或 nano sniffer.py / vim sniffer.py
```

**Task 1.1A 版本（基础版）**：

```python
#!/usr/bin/env python3
from scapy.all import *

def print_pkt(pkt):
    pkt.show()

# 把 br-c93733e9f913 替换成你 1.5 节查到的自己的接口名
pkt = sniff(iface='br-c93733e9f913', filter='icmp', prn=print_pkt)
```

保存后赋予执行权限：

```bash
chmod a+x sniffer.py
```

### 2.2 用 root 运行（应成功）

**终端 1**（启动嗅探器）：

```bash
sudo ./sniffer.py
```

程序会卡住不动（正在监听），这是正常现象。

**终端 2**（另开一个终端，制造流量）：

```bash
# 从 VM ping 一个容器
ping -c 3 10.9.0.5
```

**终端 1** 应该立刻打印出 ICMP 包的详细字段，例如：

```
###[ IP ]###
  version   = 4
  ihl       = 5
  tos       = 0x0
  len       = 84
  id        = 12345
  flags     =
  frag      = 0
  ttl       = 64
  proto     = 1
  chksum    = 0x....
  src       = 10.9.0.1
  dst       = 10.9.0.5
  ...
###[ ICMP ]###
  type      = echo request
  code      = 0
  chksum    = 0x....
  id        = 0x....
  seq       = 1
  ...
```

按 `Ctrl+C` 停止嗅探器。

📸 **截图 7**：root 运行下成功捕获 ICMP 包的完整输出（左侧 root 窗口 + 右侧 ping 窗口）。

### 2.3 用普通用户 seed 运行（应失败）

```bash
# 切换到 seed 账户
su seed
cd ~/Labsetup/volumes
./sniffer.py
```

**预期观察**：程序报错，典型错误信息类似：

```
PermissionError: [Errno 1] Operation not permitted
```

或

```
OSError: [Errno 13] Permission denied
```

**解释（写进报告）**：

- 抓包需要把网卡设置为**混杂模式（promiscuous mode）**并打开原始套接字（raw socket），这些操作在 Linux 上属于特权操作，只有 root（或具有 `CAP_NET_RAW` 能力的进程）才能执行；
- 普通 `seed` 账户没有该权限，因此无法打开接口；
- 这正说明了一条**防御原则**：混杂模式抓包依赖特权访问，所以主机加固和最小权限账户策略是有效的安全控制。

📸 **截图 8**：`su seed` 后运行报 `Permission not permitted` 的报错。

### 2.4 Task 1.1B：三种 BPF 过滤器

> 规则：**每个过滤器单独演示一次**（单独的截图）。BPF 语法写在 `filter='...'` 里。

修改 `sniffer.py` 的 `filter` 参数（或者做三个副本 `sniffer_icmp.py`、`sniffer_tcp.py`、`sniffer_net.py`，推荐后者，报告里好整理）。

#### 过滤器 ①：只抓 ICMP

```python
pkt = sniff(iface='br-c93733e9f913', filter='icmp', prn=print_pkt)
```

验证方法（另开终端）：

```bash
ping -c 3 10.9.0.5        # 会抓到
curl http://10.9.0.5      # TCP 流量，不应被抓到
```

#### 过滤器 ②：来自特定 IP 且目的端口为 23（Telnet）的 TCP 包

```python
# 把 10.9.0.5 换成你想指定的源 IP
pkt = sniff(iface='br-c93733e9f913',
            filter='tcp and src host 10.9.0.5 and dst port 23',
            prn=print_pkt)
```

验证方法（另开终端，制造 Telnet 流量）：

```bash
# 如果容器里装了 telnet 服务，可执行：
telnet 10.9.0.5 23
# 没有 telnet 服务也没关系，可以用 nc 造 23 端口流量：
nc -w 2 10.9.0.5 23 < /dev/null
# 或者只用普通 ssh/HTTP 流量做反证：这些不应被该过滤器抓到
```

> 报告要点：BPF 中 `tcp and src host A and dst port 23` 三个条件用 `and` 连接，缺一不可；可用 `tcpdump -i br-xxx -v` 命令行版先验证过滤器是否写对。

#### 过滤器 ③：来自或去往某个子网（不要用 VM 所在子网）

作业指定示例：`128.230.0.0/16`（RIT 的子网）。

```python
pkt = sniff(iface='br-c93733e9f913',
            filter='net 128.230.0.0/16',
            prn=print_pkt)
```

> ⚠️ 不能选 `10.9.0.0/16`（VM 自己的子网）。由于 `128.230.0.0/16` 是外网地址，正常情况下不会抓到包——这也是**预期行为之一**。
>
> 想抓到包可以这样验证：用 **Task 1.2 的伪造源 IP** 技术，伪造一个 `128.230.x.x` 的源地址发包给自己；或用 tcpdump 确认过滤器语法被接受（能跑起来不报错即说明语法正确）。

📸 **截图 9/10/11**：三个过滤器各自的运行结果（含成功抓到的包，或对 ③ 的说明性验证）。

---

## 3. Task 1.2：伪造 ICMP 包（Spoofing）

### 3.1 交互式操作（推荐，便于逐步演示）

开启 root 的 Python 交互环境：

```bash
sudo python3
```

逐行输入（`>>>` 是 Python 提示符，`#` 后是说明）：

```python
>>> from scapy.all import *
>>> a = IP()                       # 创建 IP 层对象
>>> a.dst = '10.9.0.5'             # 设置目的 IP（改成你拓扑里的 Host A）
>>> b = ICMP()                     # 创建 ICMP 层，默认 type=echo request
>>> p = a / b                      # "/" 表示把 b 作为 a 的 payload 叠起来
>>> send(p)                        # 发送！
.
Sent 1 packets.
```

查看 IP 包所有字段（理解各字段含义，报告里要解释）：

```python
>>> ls(a)
```

输出示例：

```
version         : BitField (4 bits)  = 4
ihl             : BitField (4 bits)  = None
tos             : XByteField         = 0
len             : ShortField         = None
id              : ShortField         = 1
flags           : FlagsField (3 bits)= <Flag 0 ()>
frag            : BitField (13 bits) = 0
ttl             : ByteField          = 64
proto           : ByteEnumField      = 0
chksum          : XShortField        = None
src             : SourceIPField      = '127.0.0.1'
dst             : DestIPField        = '127.0.0.1'
options         : PacketListField    = []
```

### 3.2 关键步骤：伪造源 IP

```python
>>> a = IP()
>>> a.dst = '10.9.0.5'
>>> a.src = '1.2.3.4'              # ★ 伪造的源地址（任意值）
>>> b = ICMP()
>>> p = a / b
>>> p.show()                       # 发送前确认字段
>>> send(p)
.
Sent 1 packets.
```

### 3.3 用 Wireshark 验证（写进报告的证据）

1. 先在 VM 桌面启动 Wireshark（操作见第 7 节），选中接口 `br-c93733e9f913` 开始抓包；
2. 回到上面的 Python 终端 `send(p)`；
3. Wireshark 里立刻 `Ctrl+F` 或用显示过滤器 `icmp` 找到刚发的包。

**你应该观察到：**

- 有一个 **ICMP Echo Request**，其 **Source = 1.2.3.4**（你伪造的地址）、Destination = 10.9.0.5；
- 如果 Host A 存活，它会回 **ICMP Echo Reply**，而这个 Reply 的 **Destination 是 1.2.3.4**（发往伪造地址），而不是你的 VM 地址 —— 这证明接收方**根本不校验源地址是否合法**。

**报告解释要点**：

- IP 层基本不对来源做任何认证，谁都能填任意 `src`；
- 这种"源地址可伪造"的特性正是 ARP 欺骗、TCP 会话劫持、中间人攻击的基础；
- 也解释了为什么 Reply 会发给 1.2.3.4 而你的 ping 程序收不到它。

📸 **截图 12**：Wireshark 中 Source=伪造IP 的 Echo Request + 发往伪造IP 的 Echo Reply。

---

## 4. Task 1.3：自己实现 Traceroute

### 4.1 原理

- 发一个包，把 **TTL = 1**：第一跳路由器收到后 TTL 减到 0，丢弃该包并回送 **ICMP "Time-to-live exceeded" (type 11)**，其中带有路由器自己的 IP → 得到第 1 跳；
- TTL = 2 → 得到第 2 跳；
- 依次增大，直到包真正到达目标（目标回 ICMP Echo Reply 或其他响应）→ 结束。

### 4.2 方法 A：手动逐跳（适合不熟 Python 的同学）

打开两个终端：

**终端 1**：启动 Wireshark 抓 `br-c93733e9f913`，显示过滤器填 `icmp`。

**终端 2**：

```bash
sudo python3
```

```python
>>> from scapy.all import *
>>> a = IP()
>>> a.dst = '8.8.8.8'        # 选一个外网目标
>>> a.ttl = 1
>>> b = ICMP()
>>> send(a/b)
.
Sent 1 packets.
```

回到 Wireshark，找 **ICMP Type 11 (Time-to-live exceeded)** 包，展开 `Internet Protocol Version 4`，读 **Source Address** —— 这就是第 1 跳路由器。

然后 TTL 改成 2 再发一次：

```python
>>> a.ttl = 2
>>> send(a/b)
```

继续在 Wireshark 里看新的 Type 11 包的 Source，得到第 2 跳。重复直到出现 **Echo Reply**（TTL 足够大，包到达目标）。

把每跳 IP 记录到表格：

| TTL | 响应类型              | 跳数/路由器 IP               |
| --- | --------------------- | ---------------------------- |
| 1   | Time-to-live exceeded | 10.9.0.254（示例，你的网关） |
| 2   | Time-to-live exceeded | x.x.x.x                      |
| ... | ...                   | ...                          |
| n   | Echo Reply            | 8.8.8.8（到达）              |

> 先用 `ip route get 8.8.8.8` 查看你会走哪个默认网关，第一跳通常就是它。

### 4.3 方法 B：自动循环版（加分项，推荐）

新建 `traceroute.py`：

```python
#!/usr/bin/env python3
from scapy.all import *

target = '8.8.8.8'

for ttl in range(1, 20):
    ans, unans = sr(IP(dst=target, ttl=ttl) / ICMP(),
                     timeout=2, verbose=0)
    for snd, rcv in ans:
        if rcv.type == 11:            # Time-to-live exceeded
            print(f"TTL={ttl:2d}  路由器: {rcv.src}")
        elif rcv.type == 0:           # Echo reply → 到达目标
            print(f"TTL={ttl:2d}  到达目标: {rcv.src}")
            break
```

运行：

```bash
sudo python3 traceroute.py
```

预期输出类似：

```
TTL= 1  路由器: 10.9.0.254
TTL= 2  路由器: 192.168.1.1
...
TTL=12  到达目标: 8.8.8.8
```

> 说明：`sr()` 是"发送并接收"，比 `send()` 多了接收响应的功能，因此无需开 Wireshark 也能拿到结果。报告里说明这一点。

📸 **截图 13**：traceroute 的完整输出（或 Wireshark 中一连串 Type 11 包）。

---

## 5. Task 1.4：Sniff-and-then-Spoof（本作业核心）

### 5.1 任务要求回顾

- 程序跑在 **VM（Attacker）** 上，监听 LAN；
- 每当嗅探到 **任何 ICMP echo request**（不管目标 IP 是谁），立即**伪造一个 echo reply** 发回去；
- 从 **user 容器** 执行 `ping X`，无论 X 是否真实存在，ping 都会收到 reply 并显示"主机存活"。

### 5.2 编写程序

新建 `~/Labsetup/volumes/sniff_spoof.py`：

```python
#!/usr/bin/env python3
from scapy.all import *

def spoof_reply(pkt):
    # 只处理 ICMP echo request
    if ICMP in pkt and pkt[ICMP].type == 8:
        # 伪造 reply：源=原包的目的IP，目的=原包的源IP
        spoofed = IP(src=pkt[IP].dst, dst=pkt[IP].src) / \
                  ICMP(type=0, id=pkt[ICMP].id, seq=pkt[ICMP].seq) / \
                  pkt[Raw].load if Raw in pkt else \
                  IP(src=pkt[IP].dst, dst=pkt[IP].src) / \
                  ICMP(type=0, id=pkt[ICMP].id, seq=pkt[ICMP].seq)
        print(f"[+] Echo request from {pkt[IP].src} to {pkt[IP].dst}"
              f" -> spoofed reply sent")
        send(spoofed, verbose=0)

# 接口名换成你自己的 br-xxx
sniff(iface='br-c93733e9f913', filter='icmp', prn=spoof_reply)
```

> 更简洁可靠的写法（推荐直接用这个）：

```python
#!/usr/bin/env python3
from scapy.all import *

def spoof_reply(pkt):
    if pkt.haslayer(ICMP) and pkt[ICMP].type == 8:   # echo request
        reply = IP(src=pkt[IP].dst, dst=pkt[IP].src) / \
                ICMP(type=0, id=pkt[ICMP].id, seq=pkt[ICMP].seq)
        # 若原包带 payload，把 payload 也原样带回（可选）
        if pkt.haslayer(Raw):
            reply = reply / pkt[Raw].load
        send(reply, verbose=0)
        print(f"[+] spoofed reply {pkt[IP].dst} -> {pkt[IP].src}")

sniff(iface='br-c93733e9f913', filter='icmp', prn=spoof_reply)
```

权限与运行：

```bash
chmod a+x sniff_spoof.py
sudo ./sniff_spoof.py
```

程序进入监听状态。

### 5.3 从 user 容器发起三个 ping

**再开一个终端**，进入用户容器：

```bash
dockps                       # 找到 hostA/user 容器 ID
docksh <容器ID前几位>
```

在容器里依次执行三个 ping（**每个都要截图**）：

```bash
ping -c 4 1.2.3.4      # 互联网上不存在的主机
ping -c 4 10.9.0.99    # 本网段不存在的主机
ping -c 4 8.8.8.8      # 互联网上存在的主机（Google DNS）
```

同时观察 VM 上 `sniff_spoof.py` 终端打印的 `[+] spoofed reply ...`。

### 5.4 预期结果与解释（报告核心部分）

| 目标                          | ping 结果                                                | 是否被你的程序嗅探到 | 原因解释                                                                                                                                                                                                                                                      |
| ----------------------------- | -------------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.2.3.4`（外网不存在）     | ✅ 显示 reply，"主机存活"                                | **是**         | 路由器不知道 1.2.3.4 在哪，但会把包转发到默认路由；ARP 层你的 VM 只需解析**路由器**的 MAC（`ip route get 1.2.3.4` 可验证）。包经网关到达外网链路，你嗅探到 echo request 并伪造 reply，ping 因此"成功"。                                               |
| `10.9.0.99`（本网段不存在） | ❌`Destination Host Unreachable`，**没有 reply** | **否**         | 目标在`10.9.0.0/24` 同一子网，Linux **必须先用 ARP 解析出 10.9.0.99 的 MAC 地址**才能封装以太网帧。没有任何主机应答 ARP → 内核直接报"主机不可达"，**ICMP echo request 根本没有发到网上** → 你的嗅探器看不到任何请求 → 自然也没有伪造 reply。 |
| `8.8.8.8`（外网存在）       | ✅ 显示 reply                                            | **是**         | 与第一种情况相同路径（走网关），你的程序回伪造 reply；注意真实主机的正常 reply 也可能同时存在，你的伪造 reply 使 ping 稳定"成功"。                                                                                                                            |

**必做验证命令**（在容器或 VM 里）：

```bash
ip route get 1.2.3.4      # 显示走哪个网关
ip route get 10.9.0.99    # 显示走本子网（on-link），需要 ARP
ip route get 8.8.8.8
```

**Wireshark 辅助证据**：在 `br-c93733e9f913` 上同时抓包，过滤 `arp or icmp`：

- ping `10.9.0.99` 时，能看到一串 **ARP Request: Who has 10.9.0.99?** 却没有 **ARP Reply** → 证明请求卡在 ARP 层；
- ping `1.2.3.4` / `8.8.8.8` 时，能看到 **ARP 解析网关** 成功，随后出现 **ICMP Echo Request**（被你的程序捕获）以及你发出的 **伪造 Echo Reply**。

📸 **截图 14/15/16**：三个 ping 各一张（容器终端 + 程序终端最好同屏）。
📸 **截图 17**：Wireshark 中 `10.9.0.99` 的 ARP Request 无应答。
📸 **截图 18**：Wireshark 中你伪造的 Echo Reply。

### 5.5 一个常见疑问（可写进报告）

> "我 ping 的是 1.2.3.4，为什么包会出现在我 VM 的网卡上？"

答：因为攻击者容器用的是 `network_mode: host`，它与 VM 共享网络命名空间，能看到 VM 网卡 `br-xxx` 上的**全部**流量；且 10.9.0.0/24 网段的出网流量都要经过该网段的二层链路，所以 echo request 会被你捕获。

---

## 6. Wireshark 图形化操作详解

### 6.1 安装与启动

```bash
sudo apt update
sudo apt install -y wireshark
# 若安装时没允许普通用户抓包，执行：
sudo usermod -aG wireshark seed
# 然后注销并重新登录 seed 账户使组生效
```

启动（VM 桌面）：

- 点击桌面菜单 `Applications → Internet → Wireshark`；或终端执行：
  ```bash
  wireshark &
  ```

### 6.2 选择网卡开始抓包

1. 主界面会列出所有接口（`eth0`、`br-c93733e9f913`、`any` 等）；
2. **双击 `br-c93733e9f913`**（或点选后点左上角鲨鱼鳍按钮 `Start`）；
3. 开始抓包后，让另一个终端产生流量（ping / telnet / 你的脚本）；
4. 停止：点红色方块 `Stop`。

### 6.3 常用显示过滤器（注意是显示过滤器，不是 BPF）

| 用途                     | 过滤表达式                                  |
| ------------------------ | ------------------------------------------- |
| 只看 ICMP                | `icmp`                                    |
| 只看 ARP                 | `arp`                                     |
| 只看某两个 IP 之间的流量 | `ip.addr==10.9.0.1 and ip.addr==10.9.0.5` |
| 只看某条流               | `ip.src==10.9.0.1 and ip.dst==10.9.0.5`   |
| 看 ICMP 类型 11          | `icmp.type==11`                           |
| 看 TCP 23 端口           | `tcp.port==23`                            |

> 易混淆点：**BPF 过滤器**（`sniff(filter=...)`、tcpdump 用的）语法是 `tcp and src host 10.9.0.5 and dst port 23`；**Wireshark 显示过滤器**语法是 `ip.src==10.9.0.5 and tcp.dstport==23`。报告里别写混。

### 6.4 展开包详情

1. 点击列表中的一个包；
2. 下方分三层：`Frame` / `Internet Protocol Version 4` / `Internet Control Message Protocol`；
3. 逐层点开小三角，可看到 `Time to live`、`Source`、`Destination`、`Type` 等字段 —— Task 1.3、1.4 的证据都在这里。

### 6.5 导出/截取证据

- 截图：用 VM 自带截图工具（`PrtSc` 或 `Applications → Accessories → Screenshot`），或宿主机截图；
- 导出特定包：`File → Export Packet Dissections → As Plain Text...`（报告可附）；
- 保存抓包文件（可选，随报告一起交）：`File → Save As → xxx.pcapng`。

📸 所有 Wireshark 证据截图记得包含：**过滤器栏**（能看到你输入的过滤表达式）+ **包列表** + **下方字段详情**。

---

## 7. 截图清单（对照打勾）

- [ ] 📸 1：SEED VM 成功启动并登录
- [ ] 📸 2：Labsetup 目录内容 + docker-compose.yml 关键配置
- [ ] 📸 3：`dockps` 显示所有容器在运行
- [ ] 📸 4：容器内 `ping 10.9.0.1` 成功
- [ ] 📸 5：`ifconfig` 显示 `br-xxx` = 10.9.0.1
- [ ] 📸 6：Scapy `IP().show()` 测试成功
- [ ] 📸 7：Task 1.1A root 运行抓到 ICMP
- [ ] 📸 8：Task 1.1A seed 账户运行报权限错误
- [ ] 📸 9：过滤器 ① `icmp`
- [ ] 📸 10：过滤器 ② `tcp and src host X and dst port 23`
- [ ] 📸 11：过滤器 ③ `net 128.230.0.0/16`
- [ ] 📸 12：Task 1.2 伪造 src 的 Echo Request + Reply
- [ ] 📸 13：Task 1.3 traceroute 结果（TTL 递增 / Type 11）
- [ ] 📸 14：ping 1.2.3.4 成功（你的程序回了 reply）
- [ ] 📸 15：ping 10.9.0.99 失败（Unreachable）
- [ ] 📸 16：ping 8.8.8.8 成功
- [ ] 📸 17：ARP Request for 10.9.0.99 无应答
- [ ] 📸 18：你伪造发出的 Echo Reply

---

## 8. 报告写作与提交

### 8.1 报告结构建议

```
1. 实验环境（拓扑图、容器 IP、你的 br-xxx 接口名）
2. Task 1.1 Sniffing
   - 代码 + 解释
   - root vs seed 对比截图 + 权限原理说明
   - 三个过滤器：各自的 BPF 语法、抓包截图、流量制造方法
3. Task 1.2 Spoofing
   - 交互代码逐行解释（IP/ICMP/send、"/" 运算符含义）
   - Wireshark 证据 + "IP 层不认证源地址" 的安全含义
4. Task 1.3 Traceroute
   - 原理（TTL 递减 + ICMP type 11）
   - 代码/手动步骤 + 跳数表
5. Task 1.4 Sniff-and-Spoof
   - 完整代码 + 逐段解释
   - 三个 ping 的结果对比表 + ARP/路由原理解释
6. 结论与安全启示（被动 vs 主动侦察、特权访问的重要性）
```

### 8.2 提交前检查表

- [ ] 每个任务都有截图（对照第 7 节清单）
- [ ] 每段代码后面都写了**解释**（不是只贴代码）
- [ ] Task 1.1A 的**权限差异**有解释（混杂模式 / raw socket / root）
- [ ] Task 1.4 三个 IP 的**结果差异**有解释，且用到了 **ARP** 和 **`ip route get`** 的证据
- [ ] 所有截图里的接口名/IP 是**你自己的**环境，不是示例的
- [ ] 报告已按课程要求命名并提交到指定平台

### 8.3 实验收尾

```bash
# 在 ~/Labsetup 目录下
dcdown        # 关闭所有容器
# 关闭 VM
```

---

*指南依据 Lab 1 PDF（9 页）整理，覆盖全部 4 个任务与提交要求。*
