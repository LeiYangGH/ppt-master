帮我解决混乱的git

## 背景

main分支是开源项目，我之前基于它做自定义的修改，在interactive分支，
主要改动蓝图见`customize-arch-design.md`。

其中一项是针对windows。

 到目前为止，我**本地interactive分支** 的87df77b6a553b045c99a314955c843b80654bbf2（三件套 四原则）可以视作定制版的正确版（其明显特征是绝大多数md文件都是翻译成中文了的）。

但今天在另一台电脑上，对interactive分支做了个愚蠢的决定，先pull了main分支，然后rebase main。遇到了大量冲突，于是请ai帮助自动处理，我只是在每次自动打开的编辑器里确定commit消息并关闭vscode，这样操作了很多次。后来觉得以后rebase会很麻烦，就请ai把interactive分支所有commit合并为一个。看起来比较清爽，就push force了。但此时已经埋下了雷，似乎ai在rebase过程中又引入了大量main分支的、之前我已经翻译或删除的文件。

后来我又在interactive分支的基础上提交了两项改动，且推送了：

- svg的自动修复，基于一个三方python库
- 基于tavily和百度的素材特别是图片搜索保存。我的需求是要去掉其他一切搜索或图片生成，
因为每一样是免费或者中国大陆能访问的。


## 任务

现在幸运的是，我当前电脑上的**本地interactive分支**还未被污染，而且有linux分支可视作其备份。我只是fetch了origin，在remote/interactive 可以看到混乱的现状和新的希望真正引入本地的改动。

请你基于上述过程和现状，帮我重新整理interactive分支，最终目标：

- 接近linux分支+svg的自动修复+基于tavily和百度的素材搜索和图片保存。其他main分支又引入的都要排除
- 后期我决定不在和main分支 rebase了，要同步上游更新我感觉采取cherry pick之类的策略更好。总之是以我自己的分支为主。

