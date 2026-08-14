#!/usr/bin/env python3
"""
ipfs-py.py

Fetch an IPFS CID's *root block* using native libp2p + Bitswap from a fresh machine.

Strategy (per transport pass):
  - Start libp2p host (TCP pass first; QUIC pass second)
  - Bootstrap (supports /dnsaddr via resolve())
  - Run Kad-DHT (client) and continuously search for providers of the CID
  - In parallel, poll Delegated Routing (Routing HTTP V1) for providers (helper path)
  - As soon as we learn dialable multiaddrs for any candidate peer, dial and Bitswap get_block
  - Keep trying until success or timeout

This version prints more debug info:
  - periodic stats line (every ~10s)
  - provider discovery events
  - dial attempts / successes
  - bitswap attempt outcomes

Hard-coded test CID:
  bafybeido2w4vlhmnzj5hyzimaviby7bozsipgrkcf4unkkf5me4tivunwq
"""

import time
import trio
import httpx
import multiaddr

from multiformats import CID

from libp2p import new_host
from libp2p.bitswap import BitswapClient
from libp2p.kad_dht.kad_dht import KadDHT, DHTMode
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.tools.async_service import background_trio_service


# -------------------------
# Hard-coded test inputs
# -------------------------

CID_STR = "bafybeido2w4vlhmnzj5hyzimaviby7bozsipgrkcf4unkkf5me4tivunwq"

# Delegated routing endpoint (helper path)
DELEGATED_BASE = "https://delegated-ipfs.dev/routing/v1"

# How long to keep trying per pass (TCP pass + QUIC pass)
MAX_WAIT_SECS = 300.0

# DHT polling backoff (active search)
DHT_POLL_INITIAL = 0.5
DHT_POLL_MAX = 8.0

# Delegated routing polling interval (helper path; keep modest)
DELEGATED_POLL_SECS = 20.0

# Timeouts
DIAL_TIMEOUT_SECS = 10.0
BITSWAP_TIMEOUT_SECS = 60.0

# Periodic debug line cadence
DEBUG_EVERY_SECS = 10.0


# -------------------------
# Bootstrap peers
# -------------------------

BOOTSTRAP_ADDRS = [
    "/dnsaddr/sg1.bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
    "/dnsaddr/sv15.bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/am6.bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    "/dnsaddr/ny5.bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/va1.bootstrap.libp2p.io/p2p/12D3KooWKnDdG3iXw9eTFijk3EWSunZcFi54Zka4wmtqtt6rPxc8",
]


# -------------------------
# Debug stats
# -------------------------

class Stats:
    def __init__(self):
        self.lock = trio.Lock()
        self.t0 = time.monotonic()

        self.bootstrap_ok = 0
        self.bootstrap_total = 0

        self.dht_queries = 0
        self.dht_last_found = 0
        self.dht_last_found_at = None

        self.delegated_polls = 0
        self.delegated_last_found = 0
        self.delegated_last_found_at = None

        self.candidates_sent = 0

        self.dial_attempts = 0
        self.dial_success = 0

        self.bitswap_attempts = 0
        self.bitswap_success = 0

        # last activity
        self.last_event = ""

    async def note(self, **kwargs):
        async with self.lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    async def inc(self, field, delta=1):
        async with self.lock:
            setattr(self, field, getattr(self, field) + delta)

    async def set_last_event(self, msg):
        async with self.lock:
            self.last_event = msg

    async def snapshot(self):
        async with self.lock:
            return {
                "elapsed": time.monotonic() - self.t0,
                "bootstrap_ok": self.bootstrap_ok,
                "bootstrap_total": self.bootstrap_total,
                "dht_queries": self.dht_queries,
                "dht_last_found": self.dht_last_found,
                "dht_last_found_at": self.dht_last_found_at,
                "delegated_polls": self.delegated_polls,
                "delegated_last_found": self.delegated_last_found,
                "delegated_last_found_at": self.delegated_last_found_at,
                "candidates_sent": self.candidates_sent,
                "dial_attempts": self.dial_attempts,
                "dial_success": self.dial_success,
                "bitswap_attempts": self.bitswap_attempts,
                "bitswap_success": self.bitswap_success,
                "last_event": self.last_event,
            }


async def reporter(stats, label):
    while True:
        s = await stats.snapshot()
        print(
            "[dbg:{}] t={:.1f}s boot={}/{} dht(q={} last_found={} at={}) del(polls={} last_found={} at={}) "
            "cand={} dial={}/{} bitswap={}/{} last={}".format(
                label,
                s["elapsed"],
                s["bootstrap_ok"],
                s["bootstrap_total"],
                s["dht_queries"],
                s["dht_last_found"],
                "-" if s["dht_last_found_at"] is None else "{:.1f}s".format(s["dht_last_found_at"]),
                s["delegated_polls"],
                s["delegated_last_found"],
                "-" if s["delegated_last_found_at"] is None else "{:.1f}s".format(s["delegated_last_found_at"]),
                s["candidates_sent"],
                s["dial_success"],
                s["dial_attempts"],
                s["bitswap_success"],
                s["bitswap_attempts"],
                s["last_event"],
            )
        )
        await trio.sleep(DEBUG_EVERY_SECS)


# -------------------------
# Helpers
# -------------------------

def ensure_p2p_suffix(addr_str, peer_id_str):
    return addr_str if "/p2p/" in addr_str else addr_str.rstrip("/") + "/p2p/" + peer_id_str


def is_tcp_addr(addr_str):
    # Avoid ws/wss unless you explicitly enable websocket transport.
    if "/ws" in addr_str or "/wss" in addr_str:
        return False
    return "/tcp/" in addr_str


def is_quic_addr(addr_str):
    return "/quic-v1" in addr_str


async def resolve_multiaddr(ma):
    """
    Expand /dnsaddr (and friends) to concrete /ip4... addresses when supported.
    If resolve() isn't available or fails, fall back to [ma].
    """
    if hasattr(ma, "resolve"):
        try:
            res = ma.resolve()
            if hasattr(res, "__await__"):
                res = await res
            return list(res) if res is not None else [ma]
        except Exception:
            return [ma]
    return [ma]


async def connect_bootstraps(host, stats):
    ok = 0
    total = len(BOOTSTRAP_ADDRS)
    await stats.note(bootstrap_total=total)

    for addr in BOOTSTRAP_ADDRS:
        try:
            ma = multiaddr.Multiaddr(addr)
            resolved = await resolve_multiaddr(ma)
            connected_this = False
            for rma in resolved:
                try:
                    pi = info_from_p2p_addr(rma)
                    await host.connect(pi)
                    ok += 1
                    connected_this = True
                    break
                except Exception:
                    continue
            if not connected_this:
                pass
        except Exception:
            continue

    await stats.note(bootstrap_ok=ok)
    print("[bootstrap] successful connections: {}/{}".format(ok, total))
    return ok


async def http_get_json(client, url, params=None):
    r = await client.get(url, params=params)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


async def delegated_providers(client, cid_str):
    data = await http_get_json(client, DELEGATED_BASE + "/providers/" + cid_str)
    provs = data.get("Providers", []) if isinstance(data, dict) else []
    return [p for p in provs if isinstance(p, dict)]


async def delegated_peer_addrs(client, peer_id_str):
    data = await http_get_json(client, DELEGATED_BASE + "/peers/" + peer_id_str)
    peers = data.get("Peers", []) if isinstance(data, dict) else []
    if not peers:
        return []
    addrs = peers[0].get("Addrs", []) or []
    return [a for a in addrs if isinstance(a, str)]


class Candidate:
    __slots__ = ("peer_id_str", "addrs", "source")

    def __init__(self, peer_id_str, addrs, source):
        self.peer_id_str = peer_id_str
        self.addrs = addrs
        self.source = source


async def dial_one_addr(host, addr_str, peer_id_str, stats):
    """
    Dial a single multiaddr string, ensuring /p2p/<peer> suffix.
    Returns PeerInfo on success, None on failure/timeout.
    """
    full = ensure_p2p_suffix(addr_str, peer_id_str)
    try:
        pi = info_from_p2p_addr(multiaddr.Multiaddr(full))
    except Exception:
        return None

    await stats.inc("dial_attempts", 1)

    with trio.move_on_after(DIAL_TIMEOUT_SECS) as scope:
        try:
            await host.connect(pi)
            await stats.inc("dial_success", 1)
            return pi
        except Exception:
            return None

    if scope.cancelled_caught:
        return None
    return None


# -------------------------
# Producers
# -------------------------

async def producer_dht_providers(cid_obj, dht, send_chan, stats):
    """
    Active search: repeatedly query DHT for providers of CID.
    """
    key = cid_obj.digest  # bytes (multihash digest)
    sleep_s = DHT_POLL_INITIAL
    last_print = 0.0

    while True:
        await stats.inc("dht_queries", 1)
        try:
            peers = await dht.find_providers(key=key, count=20)
            n = 0 if peers is None else len(peers)

            if n:
                now = time.monotonic() - stats.t0
                await stats.note(dht_last_found=n, dht_last_found_at=now)
                await stats.set_last_event("dht providers={}".format(n))

                # Emit candidates
                for pi in peers:
                    addrs = [str(a) for a in (pi.addrs or [])]
                    peer_id_str = str(pi.peer_id)
                    if addrs:
                        await send_chan.send(Candidate(peer_id_str, addrs, "dht/providers"))
                        await stats.inc("candidates_sent", 1)

                sleep_s = DHT_POLL_INITIAL
            else:
                sleep_s = min(DHT_POLL_MAX, sleep_s * 1.6)

            # Occasional light print (in addition to reporter)
            if (time.monotonic() - last_print) > 30.0:
                print("[dht] poll complete; providers={}; next_sleep={:.2f}s".format(n, sleep_s))
                last_print = time.monotonic()

        except Exception as e:
            sleep_s = min(DHT_POLL_MAX, sleep_s * 1.6)
            await stats.set_last_event("dht error")
            if (time.monotonic() - last_print) > 30.0:
                print("[dht] error: {} ; next_sleep={:.2f}s".format(repr(e), sleep_s))
                last_print = time.monotonic()

        await trio.sleep(sleep_s)


async def producer_delegated(cid_str, send_chan, stats):
    """
    Helper path: poll delegated routing for providers.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            await stats.inc("delegated_polls", 1)
            try:
                provs = await delegated_providers(client, cid_str)
                n = len(provs)

                if n:
                    now = time.monotonic() - stats.t0
                    await stats.note(delegated_last_found=n, delegated_last_found_at=now)
                    await stats.set_last_event("delegated providers={}".format(n))

                sent_this = 0
                for p in provs:
                    pid = p.get("ID")
                    if not isinstance(pid, str) or not pid:
                        continue
                    addrs = [a for a in (p.get("Addrs") or []) if isinstance(a, str)]
                    if not addrs:
                        addrs = await delegated_peer_addrs(client, pid)
                    if not addrs:
                        continue
                    await send_chan.send(Candidate(pid, addrs, "delegated/providers"))
                    await stats.inc("candidates_sent", 1)
                    sent_this += 1

                if sent_this:
                    print("[delegated] providers={} candidates_sent={}".format(n, sent_this))
                else:
                    print("[delegated] providers={} (no dialable addrs yet)".format(n))

            except Exception as e:
                await stats.set_last_event("delegated error")
                print("[delegated] error: {}".format(repr(e)))

            await trio.sleep(DELEGATED_POLL_SECS)


# -------------------------
# Consumer
# -------------------------

async def consumer_fetch(host, bitswap, cid_obj, recv_chan, want_transport, stats):
    """
    want_transport: "tcp" or "quic"
    """
    seen = set()  # (peer_id_str, addr_str)
    last_fail_print = 0.0
    failures_since_print = 0

    async for cand in recv_chan:
        if not cand.addrs:
            continue

        if want_transport == "tcp":
            addrs = [a for a in cand.addrs if is_tcp_addr(a)]
        elif want_transport == "quic":
            addrs = [a for a in cand.addrs if is_quic_addr(a)]
        else:
            addrs = list(cand.addrs)

        if not addrs:
            continue

        for addr in addrs:
            key = (cand.peer_id_str, addr)
            if key in seen:
                continue
            seen.add(key)

            pi = await dial_one_addr(host, addr, cand.peer_id_str, stats)
            if pi is None:
                failures_since_print += 1
                # print dial failures occasionally (avoid spam)
                if (time.monotonic() - last_fail_print) > 15.0 and failures_since_print:
                    print("[dial] recent failures: {} (showing one) peer={} addr={}".format(
                        failures_since_print, cand.peer_id_str, addr
                    ))
                    last_fail_print = time.monotonic()
                    failures_since_print = 0
                continue

            # Bitswap fetch
            await stats.inc("bitswap_attempts", 1)
            await stats.set_last_event("bitswap try peer={}".format(cand.peer_id_str))
            try:
                data = await bitswap.get_block(cid_obj, pi.peer_id, timeout=BITSWAP_TIMEOUT_SECS)
                await stats.inc("bitswap_success", 1)
                print(
                    "[ok] fetched via {} peer={} addr={} bytes={}".format(
                        cand.source, cand.peer_id_str, addr, len(data)
                    )
                )
                return data
            except Exception as e:
                print("[bitswap] failed peer={} addr={} err={}".format(cand.peer_id_str, addr, repr(e)))
                continue

    raise RuntimeError("candidate channel closed without success")


# -------------------------
# One transport pass runner
# -------------------------

async def run_pass(cid_str, use_quic):
    cid_obj = CID.decode(cid_str)

    if use_quic:
        label = "QUIC"
        want_transport = "quic"
        host = new_host(enable_quic=True)
        listen_addrs = [multiaddr.Multiaddr("/ip4/0.0.0.0/udp/0/quic-v1")]
    else:
        label = "TCP"
        want_transport = "tcp"
        host = new_host()
        listen_addrs = [multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0")]

    stats = Stats()
    print("[pass] starting {} pass (max_wait={}s)".format(label, MAX_WAIT_SECS))

    with trio.move_on_after(MAX_WAIT_SECS) as overall_scope:
        async with host.run(listen_addrs=listen_addrs), trio.open_nursery() as nursery:
            # Reporter
            nursery.start_soon(reporter, stats, label)

            # Bitswap client in the pass nursery
            bitswap = BitswapClient(host)
            bitswap.set_nursery(nursery)
            await bitswap.start()

            # DHT service
            dht = KadDHT(host, DHTMode.CLIENT, enable_random_walk=True)
            async with background_trio_service(dht):
                await connect_bootstraps(host, stats)

                # Candidate channel (MUST CALL open_memory_channel)
                send_chan, recv_chan = trio.open_memory_channel(500)

                # Producers
                nursery.start_soon(producer_dht_providers, cid_obj, dht, send_chan.clone(), stats)
                nursery.start_soon(producer_delegated, cid_str, send_chan.clone(), stats)

                # Consumer
                data = await consumer_fetch(host, bitswap, cid_obj, recv_chan, want_transport, stats)

                await bitswap.stop()
                overall_scope.cancel()
                return data

    if overall_scope.cancelled_caught:
        print("[pass] {} pass timed out".format(label))
    return None


# -------------------------
# Main
# -------------------------

async def main():
    t0 = time.monotonic()
    print("[config] cid={}".format(CID_STR))
    print("[config] delegated_router={}".format(DELEGATED_BASE))

    # TCP first (often best in CI / firewalled networks)
    data = await run_pass(CID_STR, use_quic=False)
    if data is not None:
        print("[done] success via TCP, bytes={}, elapsed={:.1f}s".format(len(data), time.monotonic() - t0))
        return

    # QUIC next
    data = await run_pass(CID_STR, use_quic=True)
    if data is not None:
        print("[done] success via QUIC, bytes={}, elapsed={:.1f}s".format(len(data), time.monotonic() - t0))
        return

    raise RuntimeError("Failed to fetch within timeout (TCP + QUIC).")


if __name__ == "__main__":
    trio.run(main)
