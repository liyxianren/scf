// 练习题页面逻辑

document.addEventListener('DOMContentLoaded', function() {
    let editor;
    let currentExercise = null;

    // 获取当前语言（从练习题加载后获取，先默认python）
    let LANG = window.CURRENT_LANGUAGE || 'python';
    let editorMode = LANG === 'c' ? 'text/x-csrc' : 'python';

    // 初始化CodeMirror编辑器
    editor = CodeMirror.fromTextArea(document.getElementById('code-editor'), {
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

    // 加载练习题信息
    fetch(`/api/exercises/${exerciseId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentExercise = data.data;
                // 根据练习题的语言更新编辑器模式
                LANG = currentExercise.language || 'python';
                editorMode = LANG === 'c' ? 'text/x-csrc' : 'python';
                editor.setOption('mode', editorMode);

                renderExerciseInfo(currentExercise);
                if (currentExercise.initial_code) {
                    editor.setValue(currentExercise.initial_code);
                }
            } else {
                document.getElementById('exercise-info').innerHTML =
                    '<p class="error-message">加载失败</p>';
            }
        })
        .catch(error => {
            document.getElementById('exercise-info').innerHTML =
                '<p class="error-message">加载失败，请刷新重试</p>';
        });

    // 渲染练习题信息
    function renderExerciseInfo(exercise) {
        const difficultyText = ['', '简单', '中等', '困难'][exercise.difficulty] || '未知';
        const langBadge = exercise.language === 'c'
            ? '<span class="lang-tag lang-c">C语言</span>'
            : '<span class="lang-tag lang-python">Python</span>';
        const container = document.getElementById('exercise-info');
        container.innerHTML = `
            <div class="exercise-header">
                <h2>${exercise.title}</h2>
                ${langBadge}
                <span class="difficulty-badge difficulty-${exercise.difficulty}">${difficultyText}</span>
            </div>
            <div class="markdown-content">
                ${marked ? marked.parse(exercise.description) : exercise.description}
            </div>
        `;
    }

    // 提交答案
    document.getElementById('submit-btn').addEventListener('click', async function() {
        const code = editor.getValue();
        const btn = this;

        btn.disabled = true;
        btn.textContent = LANG === 'c' ? '编译判题中...' : '判题中...';

        const resultSection = document.getElementById('result-section');
        const resultContent = document.getElementById('result-content');

        try {
            const response = await fetch(`/api/exercises/${exerciseId}/submit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code })
            });

            const result = await response.json();
            resultSection.style.display = 'block';
            renderResult(result, resultContent);
        } catch (error) {
            resultSection.style.display = 'block';
            resultContent.innerHTML = `<p class="error-message">提交失败: ${error.message}</p>`;
        } finally {
            btn.disabled = false;
            btn.textContent = '提交答案';
        }
    });

    // 渲染判题结果
    function renderResult(result, container) {
        if (!result.success) {
            container.innerHTML = `<p class="error-message">${result.error || '判题失败'}</p>`;
            return;
        }

        let html = '';

        // 代码运行输出
        if (result.code_output || result.code_error) {
            html += '<div class="code-output-section">';
            html += '<div class="code-output-header">📤 代码运行结果</div>';
            html += '<pre class="code-output-content">';
            if (result.code_output) {
                html += escapeHtml(result.code_output);
            }
            if (result.code_error) {
                html += `<span class="code-error">${escapeHtml(result.code_error)}</span>`;
            }
            if (!result.code_output && !result.code_error) {
                html += '<span class="code-empty">(无输出)</span>';
            }
            html += '</pre></div>';
        }

        // 测试用例结果
        if (result.results && result.results.length > 0) {
            html += '<div class="test-results">';
            html += '<div class="test-results-header">📋 测试用例</div>';
            result.results.forEach(test => {
                const icon = test.passed ? '✓' : '✗';
                const className = test.passed ? 'passed' : 'failed';
                html += `
                    <div class="test-result ${className}">
                        <span class="test-icon">${icon}</span>
                        <div class="test-info">
                            <div class="test-description">${test.description || test.input || `测试用例 ${test.case_id}`}</div>
                            ${!test.passed ? `
                                <div class="test-detail">
                                    期望: ${test.expected}<br>
                                    实际: ${test.actual}
                                    ${test.error ? '<br>错误: ' + test.error : ''}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        // 总结
        const summaryClass = result.is_correct ? 'success' : 'partial';
        html += `
            <div class="result-summary ${summaryClass}">
                ${result.message || (result.is_correct ? '全部通过!' : `通过 ${result.passed_cases}/${result.total_cases}`)}
            </div>
        `;

        container.innerHTML = html;
    }

    // HTML转义函数
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 显示提示
    document.getElementById('hint-btn').addEventListener('click', async function() {
        const hintSection = document.getElementById('hint-section');
        const hintContent = document.getElementById('hint-content');

        if (hintSection.style.display === 'block') {
            hintSection.style.display = 'none';
            return;
        }

        try {
            const response = await fetch(`/api/exercises/${exerciseId}/solution`);
            const data = await response.json();

            if (data.success && data.data.hint) {
                hintContent.textContent = data.data.hint;
                hintSection.style.display = 'block';
            } else {
                hintContent.textContent = '暂无提示';
                hintSection.style.display = 'block';
            }
        } catch (error) {
            hintContent.textContent = '加载失败';
            hintSection.style.display = 'block';
        }
    });

    // 关闭提示
    document.getElementById('close-hint').addEventListener('click', function() {
        document.getElementById('hint-section').style.display = 'none';
    });

    // 显示答案
    document.getElementById('solution-btn').addEventListener('click', async function() {
        const solutionSection = document.getElementById('solution-section');
        const solutionContent = document.getElementById('solution-content');

        if (solutionSection.style.display === 'block') {
            solutionSection.style.display = 'none';
            return;
        }

        if (!confirm('确定要查看参考答案吗？建议先自己尝试完成。')) {
            return;
        }

        try {
            const response = await fetch(`/api/exercises/${exerciseId}/solution`);
            const data = await response.json();

            if (data.success && data.data.solution) {
                solutionContent.textContent = data.data.solution;
                solutionSection.style.display = 'block';
            } else {
                solutionContent.textContent = '暂无参考答案';
                solutionSection.style.display = 'block';
            }
        } catch (error) {
            solutionContent.textContent = '加载失败';
            solutionSection.style.display = 'block';
        }
    });

    // 关闭答案
    document.getElementById('close-solution').addEventListener('click', function() {
        document.getElementById('solution-section').style.display = 'none';
    });

    // 快捷键提交 (Ctrl/Cmd + Enter)
    editor.setOption('extraKeys', {
        'Ctrl-Enter': function() {
            document.getElementById('submit-btn').click();
        },
        'Cmd-Enter': function() {
            document.getElementById('submit-btn').click();
        }
    });
});

// 简单的Markdown解析器（如果marked.js没有加载）
if (typeof marked === 'undefined') {
    window.marked = {
        parse: function(text) {
            return text
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                .replace(/\n/g, '<br>');
        }
    };
}
