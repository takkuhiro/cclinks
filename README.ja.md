# cclinks

[English](README.md) | **日本語**

Claude Code のセッションに出てきたリンクを、マウスを使わずキーボードで開く。

Claude Code は `[ラベル](URL)` を**ラベルだけ**描画する。URL はターミナルのバッファに一度も
現れないため、画面をスクレイプするツール（`tmux-fzf-url`、ターミナル自身のリンク検出、
VS Code の *Open Detected Link*）はどれも見つけられない。画面上に探すものが無い。

`cclinks` は代わりにセッションのトランスクリプトを読む。そこには URL が残っている。

![cclinks in action](docs/demo.gif)

ポップアップの背後にある `Sources:` が、Claude Code が実際に描画したもの。ラベルだけで、
URL は1つも無い。選択画面にはその11件すべてが並ぶ。

矢印キーか入力で絞り込み、Enter でブラウザが開く。

## 画面スクレイプやクリックでは何が足りないのか

|                          | 画面スクレイプ | Ctrl/⌘ クリック | cclinks |
| ------------------------ | -------------- | --------------- | ------- |
| 素の URL                 | 可             | 可              | 可      |
| Markdown リンク          | **不可**       | 可¹             | 可      |
| スクロールで流れたもの   | **不可**       | **不可**        | 可      |
| ラベルでの絞り込み       | 不可           | 不可            | 可      |
| キーボードから手を離さず | 可             | **不可**        | 可      |

¹ OSC 8 ハイパーリンクを解釈するターミナルに限る（iTerm2、WezTerm、Ghostty、VS Code と
Cursor の統合ターミナル）。この場合も URL はバッファには現れず、ターミナルが別経路で保持している。

クリックでも開ける。だからこのツールの主眼はリンクに*届く*ことではなく、届くために手を
動かさないことにある。Claude が喋っている間キーボードに手を置いているなら、そのままでいい。

画面スクレイプはファイルパスや他プログラムの出力に対しては今も有効で、両者は補完し合う。
隣り合ったキーに割り当てておくとよい。

## インストール

Python 3.10 以上と [fzf](https://github.com/junegunn/fzf) が必要。

```sh
uv tool install git+https://github.com/takkuhiro/cclinks
```

pipx の場合:

```sh
pipx install git+https://github.com/takkuhiro/cclinks
```

## 使い方

```sh
cclinks              # リンクを選んで開く
cclinks --print      # 開かずに一覧を出す
cclinks --active     # 最後に入力したセッションを使う（下記の hook が必要）
cclinks --latest     # 作業ディレクトリを見ず、最新のセッションを使う
cclinks --cwd PATH   # 指定したディレクトリのセッションを対象にする
cclinks --no-color   # 色を付けない
```

新しい順に並び、重複は除かれる。同じ URL が素の URL と Markdown リンクの両方で出てきた
場合は、ラベルのある方が残る。

### 色

ラベルと URL には別の色が付く。ラベルを追って読めるようにするため。
SGR パラメータで上書きするか、無効にできる。

```sh
CCLINKS_LABEL_COLOR=35 cclinks   # ラベルをマゼンタに（既定は 36 のシアン）
CCLINKS_URL_COLOR=32 cclinks     # URL を緑に（既定は 90 のグレー）
cclinks --no-color
```

`--print` は常に色を付けない。パイプに繋いだときに壊れないようにするため。

### どのセッションを読むのか

既定ではカレントディレクトリに紐づくセッションを探し、無ければ最後に更新されたセッションに
落とす。`--latest` は探索自体を省く。ホットキーから起動する場合は作業ディレクトリが
当てにならないため、こちらを使う。

ただしセッションを複数開くと、どちらも別のセッションを掴むことがある。ホットキーから起動した
選択画面は Claude Code の子ではなく*兄弟*のプロセスなので `CLAUDE_CODE_SESSION_ID` が届かず、
また同じ作業ディレクトリを複数のセッションが共有することも珍しくない。更新時刻も当てにならない。
裏で長いタスクを回しているタブは書き込みが続くため、こちらが読んでいる間に最新を奪ってしまう。

`--active` は最後に入力したセッションを使う。目の前のタブにずっと近い。
そのためにセッション自身に名乗らせるのが、次の hook。

#### hook

`contrib/user-prompt-submit-hook.sh` が、プロンプトを送るたびにセッションを記録する。
[jq](https://jqlang.github.io/jq/) が必要。好きな場所に置いて `chmod +x` し、
`~/.claude/settings.json` に次を加える。

```jsonc
"hooks": {
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash /path/to/user-prompt-submit-hook.sh",
          "timeout": 5
        }
      ]
    }
  ]
}
```

記録先は `~/.claude/cclinks-active.json`。セッション ID、トランスクリプトのパス、作業
ディレクトリだけで、プロンプト本文は含まない。場所は `CCLINKS_ACTIVE_FILE` で変えられる。

hook が無い場合、`--active` は `--latest` と同じ挙動になる。先にキーへ割り当てておいて、
後から hook を用意しても構わない。

## キーへの割り当て

Claude Code がターミナルを占有しているので、選択画面は別の場所で動かす必要がある。
環境に合うものを選ぶ。

以下の例は準備の要らない `--latest` で書いてある。hook を入れたら `--active` に変えるとよい。

### tmux

`display-popup` には tmux 3.2 以上が必要。

```tmux
bind-key u display-popup -E -w 80% -h 60% "cclinks --latest"
```

ポップアップはシェルの rc を読まないため、tmux サーバーが起動したときの PATH に依存する。
一瞬で消える場合は絶対パスで書く。

### シェルのエイリアス

```sh
alias ccl='cclinks'
```

### VS Code / Cursor のタスク

設定は2ファイル。どちらもワークスペースではなくユーザー側に置く。フォルダを開いていない
ウィンドウでもキーが効くようにするため。

まずタスクを `~/Library/Application Support/Cursor/User/tasks.json`（VS Code なら `Cursor` の
代わりに `Code`）に置く。

```jsonc
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "cclinks",
      "type": "shell",
      "command": "${userHome}/.local/bin/cclinks --latest",
      "options": {
        "env": { "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${env:PATH}" }
      },
      "presentation": {
        "echo": false, "reveal": "always", "focus": true,
        "panel": "dedicated", "close": true, "clear": true, "showReuseMessage": false
      },
      "problemMatcher": []
    }
  ]
}
```

タスクのシェルは対話シェルの `PATH` を引き継がない。コマンドと `PATH` を明示しているのは
そのため。

次にキーを、隣の `keybindings.json` に。

```jsonc
{
  "key": "alt+cmd+q",
  "command": "workbench.action.tasks.runTask",
  "args": "cclinks",
  "when": "terminalFocus"
}
```

`terminalFocus` はキーをターミナルに限定する。編集中はこのキーが空くということ。
ウィンドウのどこからでも呼びたい場合は外す。

### Raycast

スクリプトディレクトリにスクリプトコマンドを置き、ホットキーを割り当てる。

```sh
#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title cclinks
# @raycast.mode silent
open -a Terminal "$HOME/.local/bin/cclinks --latest"
```

## 開発

```sh
uv sync
uv run pytest
```

## 制約

- 対応するのは Claude Code のトランスクリプト（`~/.claude/projects/**/*.jsonl`）のみ。
- トランスクリプトは応答の完了時に書かれるため、リンクを選べるのは Claude が話し終えた後。
- ブラウザの起動には `open` / `xdg-open` を使う。macOS と tmux 3.6 で確認済み。

## ライセンス

MIT
