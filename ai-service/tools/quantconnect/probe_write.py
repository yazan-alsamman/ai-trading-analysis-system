# QuantConnect Research notebook: can the notebook write a file you can download?
# Run, then look for test_write.csv in the project's file list (EXPLORER on the right).
import os

print("working folder:", os.getcwd())
os.makedirs("gc_flow", exist_ok=True)
with open("gc_flow/test_write.csv", "w") as f:
    f.write("a,b\n1,2\n")
print("files:", os.listdir("."), os.listdir("gc_flow"))
