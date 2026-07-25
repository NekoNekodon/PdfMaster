from pathlib import Path
import os

# __file__ = H:\VuePDFedit\pdf-back\test.py
file_path = Path(__file__).resolve()
# 父级就是 pdf-back，这才是后端项目根目录
BASE_DIR = file_path.parent

print("正确后端根目录:", BASE_DIR)
target = BASE_DIR / "static" / "assets" / "index-BHCzHG63.css"
print("静态文件完整路径:", target)
print("文件是否存在:", os.path.exists(target))