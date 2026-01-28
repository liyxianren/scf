import sys
import io
import traceback
import threading
import queue
from contextlib import redirect_stdout, redirect_stderr


class CodeExecutor:
    """Python代码执行器"""

    def __init__(self, timeout=5):
        """
        初始化代码执行器
        :param timeout: 执行超时时间（秒）
        """
        self.timeout = timeout

    def execute(self, code: str, stdin_input: str = "") -> dict:
        """
        执行Python代码
        :param code: 要执行的代码
        :param stdin_input: 标准输入
        :return: 执行结果字典
        """
        result_queue = queue.Queue()

        # 预先创建StringIO对象
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        stdin_capture = io.StringIO(stdin_input)

        def run_code():
            # 保存原始的标准输入输出
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            old_stdin = sys.stdin

            # 重定向标准输入输出（使用外部创建的StringIO对象）
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            sys.stdin = stdin_capture

            error = None
            try:
                # 创建执行环境，包含自定义的input函数
                def custom_input(prompt=""):
                    # 如果有提示符，先输出到stdout
                    if prompt:
                        sys.stdout.write(str(prompt))
                    # 从stdin读取一行
                    line = stdin_capture.readline()
                    if line:
                        return line.rstrip('\n')
                    raise EOFError("没有更多输入了")

                exec_globals = {
                    '__builtins__': __builtins__,
                    '__name__': '__main__',
                    'input': custom_input  # 覆盖内置input函数
                }
                exec(code, exec_globals)
            except EOFError as e:
                # 输入不足的错误，给出友好提示
                error = f"输入不足：你的代码调用了太多次 input()，但测试用例没有提供足够的输入数据。\n请检查你的 input() 调用次数是否正确。"
            except Exception as e:
                error = traceback.format_exc()
            finally:
                output = stdout_capture.getvalue()
                error_output = stderr_capture.getvalue()

                # 恢复标准输入输出
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                sys.stdin = old_stdin

                # 组合错误信息
                final_error = None
                if error:
                    final_error = error
                elif error_output:
                    final_error = error_output

                result_queue.put({
                    'output': output,
                    'error': final_error,
                    'success': error is None and not error_output
                })

        # 使用线程执行，实现超时控制
        thread = threading.Thread(target=run_code)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout)

        if thread.is_alive():
            return {
                'output': '',
                'error': f'执行超时（超过{self.timeout}秒），请检查是否有死循环',
                'success': False,
                'timeout': True
            }

        try:
            return result_queue.get_nowait()
        except queue.Empty:
            return {
                'output': '',
                'error': '执行出错',
                'success': False
            }
