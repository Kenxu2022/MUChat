# 介绍
"[AI民大](http://so.muc.edu.cn/aiqah5/#/index)"是中央民族大学大学向校内师生提供的大模型对话服务。  
本项目将"AI民大"平台提供的`Deepseek-R1`大模型转换成兼容 OpenAI 格式的 API 端点，并可以通过 CLI 界面直接使用。  
觉得咱们学校的 WebUI 过于丑陋？不支持 LaTeX 显示？不想每天都登录一次？不如通过本项目使用更漂亮的第三方软件/WenUI 调用吧～  

# 功能
- 自动登录，并在检测到登录状态失效的时候自动刷新令牌
- 非流式/流式输出
- 原生的上下文管理，并可配置本地存储上下文的方式

# 使用
首先将本项目克隆到本地  
```
https://github.com/Kenxu2022/MUChat.git
```
确保安装好并启用 Python 虚拟环境，安装依赖
```
pip install -r requirements.txt
```
将`config.template.ini`改为`config.ini`，并配置用户名与密码 (与信息门户登录信息相同)  
运行`main.py`即可通过 CLI 界面与大模型对话，运行`api.py`即可启动 API 服务端  
可以在配置文件中修改 API 服务的监听地址与端口，并调整上下文的存储策略  
详细的 API 调用指南可直接参考[OpenAI 的文档](https://platform.openai.com/docs/api-reference/chat)

# 注意
- 使用第三方软件调用 API 时，地址填入配置文件内的监听地址与端口 (默认为`127.0.0.1:8000`)，密钥可随意填写。
- 本项目提供的 API 端点只支持获取用户输入的问题 (即对应到请求中`role: user`下的`content`) 与是否启用流式输出，其他参数与内容将会忽略。因此请将系统提示词中和用户输入的问题放在一起  
- 本项目 (以及目前学校提供的模型) 只支持文字输入，请不要输入图片  
- API 端点会在返回内容中加入使用信息，包括输入 token，输出 token(不含思考过程)，响应时间。如果启用了流式输出，则会将使用信息放在最后一个 chunk 中 (与 OpenAI API 的行为相同)

# 许可证
GNU GPLv3