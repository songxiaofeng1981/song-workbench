# Song 的项目工作台

[打开工作台](https://songxiaofeng1981.github.io/song-workbench/)

页面展示账号名下最近推送的 5 个公开项目。首张宽卡显示最新推送的项目。标题下可按 Chrome 插件、视频工具和其他工具筛选，数量按当前展示的项目计算。

## 配置和刷新

- [workbench.json](workbench.json) 设置展示数量、排除名单和项目的分类、说明与图标。公开项目自动进入候选列表，已归档仓库和 fork 会被过滤。未单独配置的项目会读取公开仓库描述，根据仓库主题分类。
- [Pages 工作流](.github/workflows/pages.yml) 在北京时间周一至周五 09:13–17:13 每小时运行一次。在 Actions 中也可以手动运行。页面中的「数据刷新」记录最近一次成功发布所用的数据抓取时间。
- [页面模板](site/index.template.html) 保存工作台布局和样式。脚本生成的静态页面由 GitHub Pages 托管。

## 本地查看

运行 `python3 scripts/build.py`，然后打开生成的 `dist/index.html`。
