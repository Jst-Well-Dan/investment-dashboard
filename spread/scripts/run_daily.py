"""每日流水线：抓数 → 出 spread.html。

    python scripts/run_daily.py            # 增量抓数 + 重出页面
    python scripts/run_daily.py --full     # 强制全量重抓
    python scripts/run_daily.py --rebuild  # 不抓数，只重出页面
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PY = sys.executable


def run(args):
    print(f"\n$ python {' '.join(args)}", flush=True)
    t0 = time.time()
    r = subprocess.run([PY] + args, cwd=ROOT)
    if r.returncode:
        print(f"  ✗ 失败（{time.time()-t0:.1f}s）", flush=True)
        sys.exit(r.returncode)
    print(f"  ✓ {time.time()-t0:.1f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="全量重抓，忽略缓存与 TTL")
    ap.add_argument("--rebuild", action="store_true", help="跳过抓数，只重出页面")
    ap.add_argument("--only", default="all", help="只刷某一组：idx / basic / rates / legu")
    a = ap.parse_args()

    t0 = time.time()
    if not a.rebuild:
        args = ["scripts/fetch_data.py"]
        if a.full:
            args.append("--force")
        if a.only != "all":
            args += ["--only", a.only]
        run(args)
    run(["scripts/build_ev.py"])
    run(["scripts/build_status.py"])
    print(f"\n全部完成，{time.time()-t0:.1f}s\n"
          f"  → docs/spread.html\n  → docs/status.html")


if __name__ == "__main__":
    main()
