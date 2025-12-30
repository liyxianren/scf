// 代码练习场编辑器逻辑

document.addEventListener('DOMContentLoaded', function() {
    // 初始化CodeMirror编辑器
    const editor = CodeMirror.fromTextArea(document.getElementById('code-editor'), {
        mode: 'python',
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

    // 运行代码
    runBtn.addEventListener('click', async function() {
        const code = editor.getValue();

        // 检测是否需要输入，弹窗收集
        let userInput = '';
        try {
            userInput = await window.pythonInputDialog.collectAllInputs(code);
        } catch (e) {
            if (e.message === 'cancelled') {
                // 用户取消了输入
                return;
            }
        }

        outputEl.textContent = '运行中...';
        outputEl.className = 'output-area';
        runBtn.disabled = true;
        runBtn.textContent = '运行中...';

        try {
            const response = await fetch('/api/code/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code, input: userInput })
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
            runBtn.textContent = '运行代码';
        }
    });

    // 清空输出
    clearBtn.addEventListener('click', function() {
        outputEl.textContent = '点击"运行代码"查看结果...';
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
