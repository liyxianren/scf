import os
import subprocess
import tempfile
import uuid


class CExecutor:
    """C语言代码编译执行器"""

    def __init__(self, compile_timeout=10, run_timeout=5):
        """
        初始化C代码执行器
        :param compile_timeout: 编译超时时间（秒）
        :param run_timeout: 运行超时时间（秒）
        """
        self.compile_timeout = compile_timeout
        self.run_timeout = run_timeout

    def execute(self, code: str, stdin_input: str = "") -> dict:
        """
        编译并执行C代码
        :param code: C源代码
        :param stdin_input: 标准输入
        :return: 执行结果字典
        """
        # 创建临时目录
        temp_dir = tempfile.gettempdir()
        unique_id = str(uuid.uuid4())[:8]
        source_file = os.path.join(temp_dir, f"code_{unique_id}.c")

        # Windows 和 Linux 的可执行文件扩展名不同
        if os.name == 'nt':
            binary_file = os.path.join(temp_dir, f"code_{unique_id}.exe")
        else:
            binary_file = os.path.join(temp_dir, f"code_{unique_id}")

        try:
            # 写入源代码
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # 编译
            compile_result = self._compile(source_file, binary_file)
            if not compile_result['success']:
                return compile_result

            # 执行
            return self._run(binary_file, stdin_input)

        finally:
            # 清理临时文件
            self._cleanup(source_file, binary_file)

    def _compile(self, source_file: str, binary_file: str) -> dict:
        """编译C代码"""
        try:
            # 使用 gcc 编译
            # -Wall: 显示所有警告
            # -o: 输出文件
            # -lm: 链接数学库
            result = subprocess.run(
                ['gcc', '-Wall', '-o', binary_file, source_file, '-lm'],
                capture_output=True,
                text=True,
                timeout=self.compile_timeout
            )

            if result.returncode != 0:
                # 编译失败
                error_msg = result.stderr.strip()
                # 简化错误信息，移除临时文件路径
                error_msg = self._simplify_error(error_msg, source_file)
                return {
                    'success': False,
                    'output': '',
                    'error': f"编译错误:\n{error_msg}",
                    'compile_error': True
                }

            # 编译成功，可能有警告
            warnings = result.stderr.strip() if result.stderr else None
            return {
                'success': True,
                'warnings': self._simplify_error(warnings, source_file) if warnings else None
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': f'编译超时（超过{self.compile_timeout}秒）',
                'timeout': True
            }
        except FileNotFoundError:
            return {
                'success': False,
                'output': '',
                'error': '编译器未找到，请确保已安装 gcc',
                'compile_error': True
            }

    def _run(self, binary_file: str, stdin_input: str) -> dict:
        """执行编译后的程序"""
        try:
            result = subprocess.run(
                [binary_file],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=self.run_timeout
            )

            output = result.stdout
            stderr = result.stderr.strip()

            # 检查返回码
            if result.returncode != 0:
                # 处理常见错误
                error_msg = self._get_runtime_error(result.returncode, stderr)
                return {
                    'success': False,
                    'output': output,
                    'error': error_msg
                }

            return {
                'success': True,
                'output': output,
                'error': stderr if stderr else None
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': f'运行超时（超过{self.run_timeout}秒），请检查是否有死循环',
                'timeout': True
            }

    def _get_runtime_error(self, return_code: int, stderr: str) -> str:
        """解析运行时错误"""
        # Linux 信号错误码
        error_messages = {
            -6: '程序异常终止 (SIGABRT)',
            -8: '浮点运算错误 (SIGFPE)，可能是除以零',
            -9: '程序被强制终止 (SIGKILL)',
            -11: '段错误 (SIGSEGV)，可能是访问了无效内存地址',
            139: '段错误 (Segmentation Fault)，请检查数组越界或空指针',
            136: '浮点异常，请检查是否有除以零操作',
        }

        if return_code in error_messages:
            return error_messages[return_code]

        if stderr:
            return f"运行错误 (返回码 {return_code}):\n{stderr}"

        return f"程序异常退出 (返回码 {return_code})"

    def _simplify_error(self, error: str, source_file: str) -> str:
        """简化错误信息，移除临时文件路径"""
        if not error:
            return error
        # 将临时文件路径替换为 "main.c"
        filename = os.path.basename(source_file)
        error = error.replace(source_file, 'main.c')
        error = error.replace(filename, 'main.c')
        return error

    def _cleanup(self, source_file: str, binary_file: str):
        """清理临时文件"""
        try:
            if os.path.exists(source_file):
                os.remove(source_file)
            if os.path.exists(binary_file):
                os.remove(binary_file)
        except Exception:
            pass  # 忽略清理错误
