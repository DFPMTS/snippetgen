# 2026-04-12 `git push -u origin master` 调试记录

## 目标

排查为什么在 `/home/dfpmts/XS/framework/snippetgen-demo` 执行：

```bash
git push -u origin master
```

会失败。

## Status Update

这份记录前半段保留了最初调查过程，但后续更深的对照实验已经推翻了“`75e2faf` 本身就是坏提交对象”这个早期假设。

截至 2026-04-12 当天更深一轮调试结束时，更准确的结论是：

- 原始对象图最终是可以被 GitHub 接受的。
- 失败更像是 GitHub 在“冷远端首次接收这整段历史对象”时，对某些 pack/object 组合的接收存在不稳定行为。
- 把对象分段送入远端后，再推完整历史通常会成功。

## 初始状态

- 本地分支：`master`
- 工作树：干净
- 远端：`git@github.com:DFPMTS/snippetgen.git`
- GitHub SSH 鉴权：成功
- `git ls-remote origin`：成功
- 远端仓库权限：GitHub API 返回 `push=true`
- 远端 rulesets：空

## 稳定复现

原命令稳定失败，报错如下：

```text
Connection to github.com closed by remote host.
send-pack: unexpected disconnect while reading sideband packet
fatal: the remote end hung up unexpectedly
```

带 `GIT_TRACE` 和 `ssh -vvv` 的日志显示：

- 本地 `pack-objects` 成功
- SSH 公钥认证成功
- GitHub `receive-pack` 能正常开始协商
- 失败发生在 pack 基本发送完成之后

额外证据：

- 本地仓库 `echo HEAD | git pack-objects --stdout --revs | wc -c` 输出 `168794`
- SSH 详细日志里失败前累计发送约 `167764` 字节

这说明不是“中途连不上”，而是 GitHub 基本收完整个 pack 后，在服务端校验/入库阶段断开。

## 试过的路径

### 1. 基础连通性

- `ssh -T git@github.com`：成功
- `git ls-remote origin`：成功
- `git remote show origin`：成功，`HEAD branch: (unknown)`
- `git push --dry-run -u origin master`：成功

结论：不是 SSH key、仓库不存在、网络完全不通这类问题。

### 2. 常见 Git 参数排查

- `git push --no-thin -u origin master`：失败
- `git -c pack.threads=1 -c core.compression=0 push -u origin master`：失败
- `git push -u origin master:main`：失败
- `git push -u origin HEAD:refs/heads/test-debug-push`：失败

结论：不是 `master/main` 分支名、不是 thin pack、不是压缩或线程参数。

### 3. SSH 443 通道对照

- `ssh -T -p 443 git@ssh.github.com`：成功
- `git push` 经 `ssh.github.com:443` 实际上传：仍失败

结论：不是 22 端口链路特有问题。

### 4. HTTPS 对照

- 读操作 `git ls-remote https://github.com/DFPMTS/snippetgen.git`：成功
- 用环境里的 `GITHUB_PAT_TOKEN` 做 HTTPS push dry-run：403，提示 token 对该仓库无写权限

结论：这个 token 不能用于写入；但 SSH 路径本身已有写权限。

### 5. 仓库健康检查

- `git fsck --full`：通过
- `git count-objects -vH`：对象很小，约 `1.88 MiB`
- 大对象扫描：没有接近 GitHub 限制的大文件
- 粗略 secret regex 扫描：未发现明显 token / private key

结论：不是对象损坏，也不是大文件限制。

### 6. “是不是任何真实上传都会失败” 对照

新建一个最小临时仓库，只包含一个 `README.md`，然后推到：

- `debug/tiny-push-probe`

结果：成功。

结论：GitHub 仓库本身、当前机器、SSH 上传路径都可以正常完成真实 push。问题只和原仓库这组历史对象有关。

### 7. “是不是当前工作树内容有问题” 对照

把当前工作树重新拷成一个新仓库，只保留当前文件内容，不带原历史，再 push：

- 第一次到 `debug/tree-push-probe`：失败
- 第二次到 `debug/tree-push-probe-2`：成功

这个探针说明：

- 当前文件内容本身不是稳定触发条件
- 原仓库历史对象仍然是主要嫌疑

### 8. 历史二分定位

按提交历史做二分，结果如下：

- 推到第 16 个提交 `c86312e`：成功
- 推到第 20 个提交 `868e889`：成功
- 推到第 22 个提交 `13608cb`：成功
- 推到第 23 个提交 `95ac4b3`：成功
- 推到第 24 个提交 `75e2faf`：失败

由此可得：

- **第一个触发失败的提交是 `75e2faf Add fixed-code multi-seed run plan`**

该提交只新增了两个文件：

- `docs/2026-04-10-fixed-code-multi-seed-run-plan.md`
- `docs/2026-04-10-fixed-code-multi-seed-run-requirements.md`

但进一步探针显示，这两个文件单独放进一个全新仓库再 push 是成功的。

结论：问题不是“这两个 markdown 文件内容单独就一定会触发 GitHub 拒绝”。

### 9. 关键判定：重建第 24 个提交对象

从第 23 个提交出发，把第 24 个提交的补丁重新生成一个新的提交对象，再 push：

- 本地误推到本地路径一次，随后修正
- 推到 GitHub 分支 `debug/history24-recreated-gh`：成功

再进一步，把第 24 到第 32 个提交整段 cherry-pick 重放成新历史，再 push：

- 推到 `debug/rewrite-probe`：成功

## 第一轮结论（已被后续实验部分推翻）

`git push -u origin master` 失败，不是因为：

- SSH key 错误
- GitHub 仓库无写权限
- 网络不通
- `master/main` 分支名
- 仓库过大
- 当前工作树文件内容本身稳定违规

当时的局部证据支持以下假设：

- **GitHub 在接收原历史时，会在包含原始提交对象 `75e2faf` 的那段历史附近异常断开。**
- **把从 `75e2faf` 开始的历史重写成新的提交对象后，完整分支可以正常 push。**

因此，最实际的 workaround 是：

- 从 `95ac4b3` 之后开始重写历史
- 至少重建 `75e2faf`
- 更稳妥的是把 `75e2faf..HEAD` 整段重放成新提交对象后再 push

## Deep Debug Follow-Up

后续做了更严格的对照后，发现上面的“`75e2faf` 就是根因”并不成立。

### 新证据 1：原始 `75e2faf` 最终可以被正常 push

在远端已经拥有相同 `parent` 和相同 `tree` 之后，再次 push 原始：

- `75e2fafd0127d3c0dd1aa662d8f59d6531e42860`

结果成功。

这说明：

- 原始 commit object 不是永久非法对象
- GitHub 最终可以接受它

### 新证据 2：原始 `HEAD` 也最终可以被正常 push

在 `snippetgen` 远端已经逐步拥有更多前缀历史和等价对象之后，再 push 原始：

```bash
git push -u origin master
```

结果成功。

也就是说：

- 原始 `master` 历史本身最终是可接受的
- 不是“这条历史永远推不上去”

### 新证据 3：冷远端首次整体接收时更容易失败

更深的对照里，首次把这条完整 `snippetgen` 历史整体推向一个尚未拥有这些对象的远端时，失败会复现。

而把较短的历史前缀先送进去，再补推完整 `HEAD`，成功率明显更高。

这说明问题更像：

- 冷远端首次接收这一整段历史对象时
- GitHub 在某种 pack / delta / unpack 组合下不稳定
- 分段推送改变了对象基线和 pack 形态，于是绕开了问题

### 新证据 4：本地 pack 形态差异明显

在本地对 `master` 做非 thin pack 对照：

- 冷启动全量包：约 `166K`
  - `238` 个非 delta 对象
  - delta 链长度分布最高到 `6`
- 远端若已拥有 `history-16` 前缀，再补 `HEAD`：
  - 包约 `94K`
  - `130` 个非 delta 对象
  - 最高 delta 链长度到 `4`
- 远端若已拥有 `history-23` 前缀，再补 `HEAD`：
  - 包约 `69K`
  - `103` 个非 delta 对象
  - 最高 delta 链长度到 `4`

这不能直接证明 GitHub 的具体 bug 在哪里，但能说明：

- 分段推送显著改变了首次传输的 pack 结构
- 问题更像接收端对“冷启动大包”的处理不稳定，而不是某个对象本身内容违规

## 更新后的结论

截至当前证据，最合理的解释是：

- **这是 GitHub 接收这组对象时的冷启动/首包不稳定问题，而不是仓库里某个提交永久非法。**
- **“重写历史后能推”之所以成立，更多是因为它改变了对象图和传输包形态，而不一定是因为原始提交内容有错。**
- **“先推较短前缀，再推完整历史”也能让原始历史成功，进一步支持这是 pack/unpack 路径问题。**

## 建议的可执行修复方案

如果要让一次首次 push 更稳，优先建议：

1. 先把较短前缀历史推上远端，再推完整 `master`。
2. 如果前缀分段不可接受，再考虑重写历史来改变对象图和 pack 形态。
3. 不要再把“`75e2faf` 一定坏了”作为根因假设。

调试中验证过的可行思路包括：

```bash
git push origin c86312e65789fa0efb917c33cd69c23180ba84d3:refs/heads/<prefix-branch>
git push -u origin master
```

以及：

```bash
git reset --hard 95ac4b31c407accee891f78372d711ec6b22146f
git cherry-pick 75e2fafd0127d3c0dd1aa662d8f59d6531e42860^..0309073442fa3794954b5ea0b600d752934f49dd
git push origin HEAD:<new-branch>
```

前者更像 workaround；后者更像通过改写对象图来绕过接收端问题。

## 调试过程中创建的远端探针分支

以下分支已被推到 GitHub 远端：

- `debug/docs24-probe`
- `debug/history-16`
- `debug/history-20`
- `debug/history-22`
- `debug/history-23`
- `debug/history24-recreated-gh`
- `debug/probe-a1`
- `debug/probe-a2`
- `debug/rewrite-probe`
- `debug/subset-a-probe`
- `debug/subset-b-probe`
- `debug/tiny-push-probe`
- `debug/tree-push-probe-2`

本地临时探针分支已经清理，只保留了 `master`。
