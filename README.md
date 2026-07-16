# Hermes Agent Devcontainer

Windows native Ollama + CodeRouter経由でHermes Agentを動かすDevContainer構成。

## 構成

```
Devcontainer(Linux, Hermes Agent)
  → http://host.docker.internal:8088/v1 (OpenAI互換 chat_completions)
  → CodeRouter(Windows host, port 8088)
    → Ollama (Windows native, localhost:11434)
    → NVIDIA NIM
    → OpenRouter (free)
```

Hermes Agentは自身の設定・記憶・skillsをDocker named volume (`hermes-agent-home`) に永続化する。CodeRouterがOllama/NIM/OpenRouterへのプロバイダ切替・fallbackを担当し、Hermes側は単一のcustom OpenAI互換エンドポイントとしてのみ認識する。

## 前提

- Windows 11 + Docker Desktop (WSL2 backend)
- VS Code + Dev Containers拡張
- Windows native Ollama インストール・設定済み
- CodeRouter (`pip install coderouter-cli`) インストール・`providers.yaml`設定済み

## ディレクトリ構成

```
プロジェクトルート/
├── .devcontainer/
│   └── devcontainer.json
├── .gitignore
└── README.md
```

Hermes Agentの`~/.hermes/`はコンテナ内のnamed volumeに配置され、プロジェクトルート上には存在しない（NTFSバインドマウントは`chmod`が効かないため不採用）。

## `.devcontainer/devcontainer.json`

```json
{
  "name": "hermes-agent",
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu-24.04",
  "features": {
    "ghcr.io/devcontainers/features/node:1": {},
    "ghcr.io/devcontainers/features/python:1": {}
  },
  "mounts": [
    "source=hermes-agent-home,target=/home/vscode/.hermes,type=volume"
  ],
  "postCreateCommand": "sudo chown -R vscode:vscode /home/vscode/.hermes && curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash",
  "remoteEnv": {
    "HERMES_HOME": "/home/vscode/.hermes"
  }
}
```

## セットアップ手順

### 1. CodeRouterをWindows側で起動

`CODEROUTER_ALLOWED_HOSTS`環境変数（Userスコープ、永続登録済み）が必要。未設定の場合は先に登録：

```powershell
[System.Environment]::SetEnvironmentVariable("CODEROUTER_ALLOWED_HOSTS", "host.docker.internal", "User")
```

登録後は新しいPowerShellウィンドウで起動するだけでよい：

```powershell
coderouter serve --host 0.0.0.0 --port 8088 --mode nim-first
```

- `--host 0.0.0.0`必須。デフォルトの`127.0.0.1`バインドだとDockerコンテナ側の`host.docker.internal`から到達不可。
- `CODEROUTER_ALLOWED_HOSTS`未設定だと`host.docker.internal`経由のリクエストがHostヘッダー検証（DNSリバインディング対策）で403拒否される。

### 2. Devcontainerを開く

VS Codeでプロジェクトフォルダを開き、F1 → `Dev Containers: Reopen in Container`。

初回はHermes Agentインストーラが自動実行される（`postCreateCommand`）。

### 3. 疎通確認

コンテナ内ターミナルで：

```bash
curl http://host.docker.internal:8088/v1/models
```

CodeRouterのproviders一覧がJSONで返ればOK。`Host ... is not allowed`エラーが出る場合はCodeRouter側の`CODEROUTER_ALLOWED_HOSTS`設定を確認。

### 4. Hermes初期設定

```bash
hermes setup
```

ウィザードで以下を選択：

| 項目 | 選択内容 |
|---|---|
| Setup mode | Full setup |
| Inference Provider | Custom OpenAI-compatible endpoint |
| API base URL | `http://host.docker.internal:8088/v1` |
| API compatibility mode | Chat Completions |
| Model name | `nim-qwen3-coder-480b`（CodeRouterのprovider名。実体は`qwen/qwen3-next-80b-a3b-instruct`） |
| Context length | 空欄（auto-detectで262K程度を検出） |
| Terminal backend | Local（devcontainer自体がサンドボックスのため） |
| Messaging platforms | 未選択（CLI利用のみ） |
| Tools | デフォルトのまま |
| Browser provider | Local Browser |
| Image generation | Skip |

### 5. 動作確認

```bash
hermes chat
```

```
❯ こんにちは、動作確認です。1+1は？
❯ 現在の作業ディレクトリのファイル一覧を見せて
```

2つ目でterminalツール（`ls -la`）が実際に呼ばれることを確認する。

## 生成された `~/.hermes/config.yaml` の要点

```yaml
model:
  default: nim-qwen3-coder-480b
  provider: custom
  base_url: http://host.docker.internal:8088/v1
  api_mode: chat_completions
terminal:
  backend: local
```

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `postCreateCommand`が`chmod: Operation not permitted`で失敗 | `.hermes`をWindowsホストへNTFSバインドマウントしていた | named volumeに変更（本構成は対応済み） |
| `mkdir: cannot create directory '.hermes/bin': Permission denied` | named volumeの初期所有者がroot | `postCreateCommand`先頭に`sudo chown -R vscode:vscode /home/vscode/.hermes`を追加（本構成は対応済み） |
| `curl`で`{"detail":"Host 'host.docker.internal:8088' is not allowed."}` | CodeRouterのDNSリバインディング対策（Hostヘッダーallowlist） | Windows側で`CODEROUTER_ALLOWED_HOSTS=host.docker.internal`を設定してからCodeRouter再起動 |
| CodeRouterに接続できない（そもそも到達しない） | `coderouter serve`が`127.0.0.1`にのみbindしている | `--host 0.0.0.0`を付けて起動 |
| `⚠ Auxiliary title generation failed: Request timed out.` | セッションタイトル生成用の補助LLM呼び出しのタイムアウト | 動作に影響なし。気になる場合は`auxiliary.title_generation`に別の高速プロバイダを設定 |
| `tirith security scanner enabled but not available` | tirithバイナリ未インストール | pattern matchingにフォールバック済み。厳格スキャンが必要なら別途`tirith`導入 |

## Hermes Dashboard（Web UI）

CLIと同じ機能をブラウザから使えるダッシュボード。

### 1. web extra インストール

デフォルトインストールにはHTTP stackが含まれないため追加が必要：

```bash
~/.hermes/bin/uv pip install -e ".[web]" --python ~/.hermes/hermes-agent/venv/bin/python
```

`~/.hermes/bin/uv`はPATHに含まれていないため、フルパス指定が必要。`--python`でHermes本体が使うvenv（`~/.hermes/hermes-agent/venv`）を明示的に指定する。

### 2. port forward（任意）

VS Codeが実行時に自動検出するため`devcontainer.json`への追記は必須ではないが、明示しておくと安定する：

```json
"forwardPorts": [9119]
```

### 3. 起動

```bash
hermes dashboard --host 0.0.0.0
```

- ループバック以外（`0.0.0.0`）にバインドする場合、認証必須（`--insecure`は非対応）。初回起動時に認証方式を聞かれる：
  - **[1] Username & password** ← ローカルLAN用途はこちらを選択
  - [2] OAuth via Nous Portal（`hermes dashboard register`が別途必要、今回のBYO構成には不要）
- `1`を選び、ユーザー名・パスワードを設定する。

### 4. アクセス

VS Codeの`PORTS`タブに`9119`が自動転送される。表示されたURL、またはブラウザで`http://localhost:9119`を開く。

## Hermes Desktop（GUIネイティブアプリ）について

DevContainer内には直接インストールしない。Linux DevContainerはヘッドレスのため、GUIアプリをコンテナ内で動かすのは非実用的。

利用したい場合はリモート接続方式で構成する：

```
Hermes Desktop (Windows native, GUI)
  → WebSocket接続 →
Hermes gateway (Devcontainer内で稼働)
```

Devcontainer側で`hermes gateway start`を起動しport forwardを設定、Windows側にHermes Desktopをインストールして「Remote Hermes」接続先を指定する。gatewayのポート番号・認証方式（OAuth vs username/password）は必要になったタイミングで別途確認。

## 既知の制約・注意点

- `CODEROUTER_ALLOWED_HOSTS`はUserスコープ環境変数。新しいPowerShellウィンドウを開かないと反映されない。
- `nim-qwen3-coder-480b`のvision対応は未確認。画像解析ツール使用時にエラーが出た場合は`auxiliary.vision`に別モデルを設定する。
- CodeRouterのモデル名は`providers.yaml`の`name`キー（例: `nim-qwen3-coder-480b`）であり、実際のモデルID（`qwen/qwen3-next-80b-a3b-instruct`）とは異なる。Hermes側の`model.default`にはCodeRouterのprovider名を指定する。
- Dashboardのweb extraはnamed volume内（`~/.hermes/hermes-agent/venv`）にインストールされるため、volumeを削除しない限り再ビルド後も再インストール不要。
