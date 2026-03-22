import PyInstaller.__main__
import os
import customtkinter

# 获取 customtkinter 的安装路径
ctk_path = os.path.dirname(customtkinter.__file__)

PyInstaller.__main__.run([
    'gui.py',
    '--name=DialogueExtractor',
    '--onefile',
    '--noconsole',
    # 包含 customtkinter 的整个资源目录
    f'--add-data={os.path.join(ctk_path, "assets")};customtkinter/assets',
    '--clean',
])
