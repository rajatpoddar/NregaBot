import compileall
import shutil
import os

# 1. Compile all .py files to .pyc
compileall.compile_dir('.', force=True, legacy=True) # legacy=True se .pyc wahi banega

# 2. Delete original .py files (Sirf dist folder me, original code mat uda dena!)
# (Behtar hoga aap pehle code ko ek 'build_temp' folder me copy karein fir ye karein)