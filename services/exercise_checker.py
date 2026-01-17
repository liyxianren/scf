import json
from .code_executor import CodeExecutor
from .c_executor import CExecutor


class ExerciseChecker:
    """练习题判题服务"""

    def __init__(self, language='python'):
        self.language = language
        if language == 'c':
            self.executor = CExecutor(compile_timeout=10, run_timeout=5)
        else:
            self.executor = CodeExecutor(timeout=5)

    def check_submission(self, code: str, test_cases_json: str) -> dict:
        """
        检查提交的代码
        :param code: 学生提交的代码
        :param test_cases_json: 测试用例JSON字符串
        :return: 判题结果
        """
        try:
            test_config = json.loads(test_cases_json)
        except json.JSONDecodeError:
            return {'success': False, 'error': '测试用例格式错误'}

        test_type = test_config.get('test_type', 'output')

        if test_type == 'output':
            return self._check_output(code, test_config.get('cases', []))
        elif test_type == 'function':
            return self._check_function(code, test_config)

        return {'success': False, 'error': '未知的测试类型'}

    def _check_output(self, code: str, cases: list) -> dict:
        """检查输出型题目"""
        results = []
        passed = 0
        # 记录第一个测试用例的完整输出作为代码运行结果展示
        code_output = ''
        code_error = ''

        for i, case in enumerate(cases):
            stdin_input = case.get('input', '')
            expected = str(case.get('expected_output', '')).strip()

            result = self.executor.execute(code, stdin_input)
            actual = result['output'].strip()

            # 保存第一个测试用例的输出用于展示
            if i == 0:
                code_output = result['output']
                code_error = result.get('error', '')

            is_passed = (actual == expected) and result['success']
            if is_passed:
                passed += 1

            results.append({
                'case_id': i + 1,
                'passed': is_passed,
                'expected': expected,
                'actual': actual,
                'error': result.get('error'),
                'description': case.get('description', f'测试用例{i + 1}')
            })

        total = len(cases)
        return {
            'success': True,
            'is_correct': passed == total,
            'total_cases': total,
            'passed_cases': passed,
            'results': results,
            'code_output': code_output,
            'code_error': code_error,
            'message': '恭喜！全部测试通过！' if passed == total else f'通过 {passed}/{total} 个测试用例'
        }

    def _check_function(self, code: str, config: dict) -> dict:
        """检查函数型题目"""
        func_name = config.get('function_name', '')
        tests = config.get('function_tests', [])
        results = []
        passed = 0
        # 记录第一个测试用例的信息用于展示
        code_output = ''
        code_error = ''

        for i, test in enumerate(tests):
            args = test.get('args', [])
            expected = test.get('expected')

            # 构造测试代码
            args_str = ', '.join(repr(arg) for arg in args)
            test_code = f"{code}\n\n__result__ = {func_name}({args_str})\nprint(repr(__result__))"

            result = self.executor.execute(test_code)

            # 保存第一个测试用例的输出用于展示
            if i == 0:
                code_output = f"调用 {func_name}({args_str}) 的返回值: {result['output'].strip()}"
                code_error = result.get('error', '')

            try:
                if result['success'] and result['output'].strip():
                    actual = eval(result['output'].strip())
                    is_passed = (actual == expected)
                else:
                    actual = result.get('error', '执行错误')
                    is_passed = False
            except Exception as e:
                actual = result['output'].strip() if result['output'] else str(e)
                is_passed = False

            if is_passed:
                passed += 1

            results.append({
                'case_id': i + 1,
                'passed': is_passed,
                'input': f'{func_name}({args_str})',
                'expected': repr(expected),
                'actual': repr(actual) if is_passed else str(actual),
                'error': result.get('error') if not is_passed else None
            })

        total = len(tests)
        return {
            'success': True,
            'is_correct': passed == total,
            'total_cases': total,
            'passed_cases': passed,
            'results': results,
            'code_output': code_output,
            'code_error': code_error,
            'message': '恭喜！全部测试通过！' if passed == total else f'通过 {passed}/{total} 个测试用例'
        }
