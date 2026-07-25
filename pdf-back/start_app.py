import webbrowser
import time
import os

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_project.settings')
    time.sleep(0.5)

    from django.core.management import execute_from_command_line
    import threading

    def run_django_server():
        # 加上 --noreload 关闭自动重载，解决signal报错
        execute_from_command_line(["", "runserver", "--noreload", "127.0.0.1:8000"])

    server_thread = threading.Thread(target=run_django_server, daemon=True)
    server_thread.start()

    time.sleep(1.6)
    webbrowser.open("http://127.0.0.1:5173")

    # 主线程阻塞保活
    while True:
        time.sleep(999)

if __name__ == "__main__":
    main()