// 代码练习场编辑器逻辑

document.addEventListener('DOMContentLoaded', function() {
    // 获取当前语言
    const LANG = window.CURRENT_LANGUAGE || 'python';
    const editorMode = LANG === 'c' ? 'text/x-csrc' : 'python';

    // 初始化CodeMirror编辑器
    const editor = CodeMirror.fromTextArea(document.getElementById('code-editor'), {
        mode: editorMode,
        theme: 'dracula',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        lineWrapping: true,
        matchBrackets: true,
        autoCloseBrackets: true
    });

    const runBtn = document.getElementById('run-btn');
    const clearBtn = document.getElementById('clear-output');
    const outputEl = document.getElementById('output');

    const runBtnText = LANG === 'c' ? '编译运行' : '运行代码';

    // 运行代码
    runBtn.addEventListener('click', async function() {
        const code = editor.getValue();

        // 检测是否需要输入，弹窗收集
        let userInput = '';
        try {
            userInput = await window.codeInputDialog.collectAllInputs(code, LANG);
        } catch (e) {
            if (e.message === 'cancelled') {
                // 用户取消了输入
                return;
            }
        }

        outputEl.textContent = LANG === 'c' ? '编译运行中...' : '运行中...';
        outputEl.className = 'output-area';
        runBtn.disabled = true;
        runBtn.textContent = LANG === 'c' ? '编译中...' : '运行中...';

        try {
            const response = await fetch('/api/code/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code, input: userInput, language: LANG })
            });

            const result = await response.json();

            if (result.success) {
                outputEl.textContent = result.output || '(程序执行完成，无输出)';
                outputEl.className = 'output-area';
            } else {
                outputEl.textContent = result.error || '执行出错';
                outputEl.className = 'output-area error';
            }
        } catch (error) {
            outputEl.textContent = '请求失败: ' + error.message;
            outputEl.className = 'output-area error';
        } finally {
            runBtn.disabled = false;
            runBtn.textContent = runBtnText;
        }
    });

    // 清空输出
    clearBtn.addEventListener('click', function() {
        const placeholder = LANG === 'c'
            ? '点击"编译运行"查看结果...\n如果代码中有 scanf()，会自动弹窗让你输入'
            : '点击"运行代码"查看结果...\n如果代码中有 input()，会自动弹窗让你输入';
        outputEl.textContent = placeholder;
        outputEl.className = 'output-area';
    });

    // 快捷键运行 (Ctrl/Cmd + Enter)
    editor.setOption('extraKeys', {
        'Ctrl-Enter': function() {
            runBtn.click();
        },
        'Cmd-Enter': function() {
            runBtn.click();
        }
    });
});
