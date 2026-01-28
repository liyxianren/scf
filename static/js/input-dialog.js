/**
 * 代码输入弹窗组件
 * 检测代码中的 input() 或 scanf() 调用，弹窗收集用户输入
 * 支持 Python 和 C 语言
 */

class CodeInputDialog {
    constructor() {
        this.modal = null;
        this.createModal();
    }

    createModal() {
        // 创建模态框HTML
        const modalHTML = `
            <div class="input-modal-overlay" id="inputModalOverlay">
                <div class="input-modal">
                    <div class="input-modal-header">
                        <h3>📝 程序需要输入</h3>
                        <button class="input-modal-close" id="inputModalClose">&times;</button>
                    </div>
                    <div class="input-modal-body">
                        <p class="input-modal-prompt" id="inputModalPrompt">请输入内容：</p>
                        <input type="text" class="input-modal-input" id="inputModalInput"
                               placeholder="在此输入..." autofocus>
                        <p class="input-modal-hint" id="inputModalHint"></p>
                    </div>
                    <div class="input-modal-footer">
                        <button class="btn btn-outline" id="inputModalCancel">取消运行</button>
                        <button class="btn btn-primary" id="inputModalSubmit">确认输入</button>
                    </div>
                </div>
            </div>
        `;

        // 添加样式
        const styleHTML = `
            <style>
                .input-modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                    opacity: 0;
                    visibility: hidden;
                    transition: all 0.3s ease;
                }

                .input-modal-overlay.show {
                    opacity: 1;
                    visibility: visible;
                }

                .input-modal {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    width: 90%;
                    max-width: 420px;
                    transform: scale(0.9) translateY(-20px);
                    transition: transform 0.3s ease;
                }

                .input-modal-overlay.show .input-modal {
                    transform: scale(1) translateY(0);
                }

                .input-modal-header {
                    padding: 16px 20px;
                    background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
                    color: white;
                    border-radius: 12px 12px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .input-modal-header h3 {
                    margin: 0;
                    font-size: 16px;
                    font-weight: 500;
                }

                .input-modal-close {
                    background: none;
                    border: none;
                    color: white;
                    font-size: 24px;
                    cursor: pointer;
                    opacity: 0.8;
                    transition: opacity 0.2s;
                    line-height: 1;
                }

                .input-modal-close:hover {
                    opacity: 1;
                }

                .input-modal-body {
                    padding: 20px;
                }

                .input-modal-prompt {
                    margin: 0 0 12px 0;
                    color: #334155;
                    font-size: 14px;
                    font-weight: 500;
                }

                .input-modal-input {
                    width: 100%;
                    padding: 12px 14px;
                    border: 2px solid #e2e8f0;
                    border-radius: 8px;
                    font-size: 15px;
                    font-family: 'JetBrains Mono', monospace;
                    transition: border-color 0.2s, box-shadow 0.2s;
                    box-sizing: border-box;
                }

                .input-modal-input:focus {
                    outline: none;
                    border-color: #0ea5e9;
                    box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
                }

                .input-modal-hint {
                    margin: 10px 0 0 0;
                    color: #64748b;
                    font-size: 12px;
                }

                .input-modal-footer {
                    padding: 16px 20px;
                    background: #f8fafc;
                    border-radius: 0 0 12px 12px;
                    display: flex;
                    justify-content: flex-end;
                    gap: 10px;
                }

                .input-modal-footer .btn {
                    padding: 10px 20px;
                    font-size: 14px;
                }
            </style>
        `;

        // 插入到页面
        document.head.insertAdjacentHTML('beforeend', styleHTML);
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // 获取元素引用
        this.modal = document.getElementById('inputModalOverlay');
        this.promptEl = document.getElementById('inputModalPrompt');
        this.inputEl = document.getElementById('inputModalInput');
        this.hintEl = document.getElementById('inputModalHint');
        this.submitBtn = document.getElementById('inputModalSubmit');
        this.cancelBtn = document.getElementById('inputModalCancel');
        this.closeBtn = document.getElementById('inputModalClose');

        // 绑定事件
        this.closeBtn.addEventListener('click', () => this.cancel());
        this.cancelBtn.addEventListener('click', () => this.cancel());
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.submit();
            }
            if (e.key === 'Escape') {
                this.cancel();
            }
        });
        this.submitBtn.addEventListener('click', () => this.submit());
    }

    /**
     * 检测代码中的输入调用次数
     * @param {string} code - 代码
     * @param {string} language - 语言 ('python' 或 'c')
     */
    static countInputCalls(code, language = 'python') {
        let cleanCode = code;

        if (language === 'c') {
            // C语言：移除注释和字符串
            // 移除多行注释 /* ... */
            cleanCode = cleanCode.replace(/\/\*[\s\S]*?\*\//g, '');
            // 移除单行注释 //
            cleanCode = cleanCode.replace(/\/\/.*/g, '');
            // 移除字符串
            cleanCode = cleanCode.replace(/"[^"\\]*(\\.[^"\\]*)*"/g, '');

            // 匹配 scanf( 调用
            const matches = cleanCode.match(/\bscanf\s*\(/g);
            return matches ? matches.length : 0;
        } else {
            // Python：移除注释和字符串中的 input
            // 移除多行字符串
            cleanCode = cleanCode.replace(/'''[\s\S]*?'''/g, '');
            cleanCode = cleanCode.replace(/"""[\s\S]*?"""/g, '');

            // 移除单行字符串
            cleanCode = cleanCode.replace(/'[^']*'/g, '');
            cleanCode = cleanCode.replace(/"[^"]*"/g, '');

            // 移除注释
            cleanCode = cleanCode.replace(/#.*/g, '');

            // 匹配 input( 调用
            const matches = cleanCode.match(/\binput\s*\(/g);
            return matches ? matches.length : 0;
        }
    }

    /**
     * 提取输入提示语
     * @param {string} code - 代码
     * @param {string} language - 语言 ('python' 或 'c')
     */
    static extractInputPrompts(code, language = 'python') {
        const prompts = [];

        if (language === 'c') {
            // C语言：scanf 没有内置提示，但我们可以查找前面的 printf
            // 简单处理：为每个 scanf 返回通用提示
            const scanfCount = CodeInputDialog.countInputCalls(code, 'c');
            for (let i = 0; i < scanfCount; i++) {
                prompts.push('请输入数据：');
            }
        } else {
            // Python：匹配 input("提示") 或 input('提示')
            const regex = /\binput\s*\(\s*(['"`])(.*?)\1\s*\)/g;
            let match;

            while ((match = regex.exec(code)) !== null) {
                prompts.push(match[2] || '请输入：');
            }

            // 匹配没有提示语的 input()
            const noPromptRegex = /\binput\s*\(\s*\)/g;
            while (noPromptRegex.exec(code) !== null) {
                prompts.push('请输入：');
            }
        }

        return prompts;
    }

    /**
     * 显示弹窗并获取输入
     */
    show(prompt = '请输入：', hint = '', currentIndex = 0, totalCount = 1) {
        return new Promise((resolve, reject) => {
            this.promptEl.textContent = prompt;
            this.hintEl.textContent = totalCount > 1
                ? `输入 ${currentIndex + 1} / ${totalCount}${hint ? ' - ' + hint : ''}`
                : hint;
            this.inputEl.value = '';

            this.resolvePromise = resolve;
            this.rejectPromise = reject;

            this.modal.classList.add('show');

            // 延迟聚焦，确保动画完成
            setTimeout(() => this.inputEl.focus(), 100);
        });
    }

    submit() {
        const value = this.inputEl.value;
        this.modal.classList.remove('show');
        if (this.resolvePromise) {
            this.resolvePromise(value);
        }
    }

    cancel() {
        this.modal.classList.remove('show');
        if (this.rejectPromise) {
            this.rejectPromise(new Error('用户取消输入'));
        }
    }

    /**
     * 收集所有输入
     * @param {string} code - 代码
     * @param {string} language - 语言 ('python' 或 'c')
     * @returns {Promise<string>} - 所有输入用换行符连接
     */
    async collectAllInputs(code, language = 'python') {
        const inputCount = CodeInputDialog.countInputCalls(code, language);

        if (inputCount === 0) {
            return '';
        }

        const prompts = CodeInputDialog.extractInputPrompts(code, language);
        const inputs = [];

        for (let i = 0; i < inputCount; i++) {
            const prompt = prompts[i] || (language === 'c' ? '请输入数据：' : '请输入：');
            try {
                const value = await this.show(prompt, '', i, inputCount);
                inputs.push(value);
            } catch (e) {
                // 用户取消
                throw new Error('cancelled');
            }
        }

        return inputs.join('\n');
    }
}

// 创建全局实例（保持向后兼容）
window.codeInputDialog = new CodeInputDialog();
window.pythonInputDialog = window.codeInputDialog;  // 兼容旧代码
