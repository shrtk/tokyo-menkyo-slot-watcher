# tokyo-menkyo-slot-watcher

警視庁の運転免許手続予約サイトの空き枠を監視するシンプルなスクリプトです。  
指定した試験場の予約カレンダーを定期的にチェックし、空きが見つかった場合に　デスクトップ通知音 及び Discord Webhookへ通知します。

私はスクリプトを動かして1時間ほどで予約が取れました。

---

## Features

- 予約カレンダーの空き枠を定期チェック
- 複数センターの同時監視
- デスクトップ 通知音
- Discord Webhook 通知
- 通知数制限
- 過去日の自動除外

対応免許センター

- 江東
- 鮫洲
- 府中

---

## Requirements

- Python 3.9+

---

## Installation

```bash
git clone https://github.com/shrtk/tokyo-menkyo-slot-watcher.git
```
---
## Usage

```bash
python watch_capacity.py
```

---

> **Note**
> `config` の `date` はデフォルトで `202603`（2026年3月）になっています。  
> 使用する際は、監視したい月に合わせて **YYYYMM 形式**で各自変更してください。
