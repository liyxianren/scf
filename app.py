import os

from app_factory import create_app


# 模块级变量，供 gunicorn / Procfile / Zeabur 引用
if os.environ.get('SCF_SKIP_APP_AUTO_CREATE') == '1':
    app = None
else:
    app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    runtime_app = app or create_app()
    runtime_app.run(debug=True, host='0.0.0.0', port=port)
