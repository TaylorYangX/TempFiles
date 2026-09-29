Lab1 task1.3

#!/usr/bin/env python3

import sys
from scapy.all import IP, ICMP, sr1, conf

if len(sys.argv) != 2:
    print(f"Usage: sudo {sys.argv[0]} <destination>")
    sys.exit(1)

destination = sys.argv[1]
max_hops = 30
timeout = 2

conf.verb = 0

print(f"Traceroute to {destination}")

for ttl in range(1, max_hops + 1):
    packet = IP(dst=destination, ttl=ttl) / ICMP()

    reply = sr1(
        packet,
        timeout=timeout,
        verbose=0
    )

    if reply is None:
        print(f"{ttl:2d}  *")
        continue

    router_ip = reply.src
    icmp_packet = reply.getlayer(ICMP)

    if icmp_packet is not None:
        print(
            f"{ttl:2d}  {router_ip} "
            f"(ICMP type={icmp_packet.type}, code={icmp_packet.code})"
        )

        # ICMP type 0: Echo Reply，说明到达目标
        if icmp_packet.type == 0:
            print("Reached destination.")
            break

        # ICMP type 3: Destination Unreachable
        if icmp_packet.type == 3:
            print("Destination unreachable.")
            break
    else:
        print(f"{ttl:2d}  {router_ip}")
