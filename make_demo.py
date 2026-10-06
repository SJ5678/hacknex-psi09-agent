import os, shutil, subprocess, pathlib, sys

src = pathlib.Path(__file__).parent / "demo" / "shop_demo"
dst = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "demo_work")
if dst.exists():
    shutil.rmtree(dst, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
shutil.copytree(src, dst)
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "commit", "-qm", "initial buggy state"]):
    subprocess.run(c, cwd=dst, check=True)
print("Ready:", dst)
