#!/usr/bin/env python3
"""Reassemble index.html: figure first, short caption under it, TOC on top.

The page had grown into long prose paragraphs with the audio buried underneath.
This rebuilds it around the figures — everything a caption used to explain is now
drawn into the waveform images by make_waves.py — and reorders the sections:

    目次 → ポスター → 音声サンプル(3条件) → 評価指標の限界
         → 今回スコープ外になったグラフ → もっとたくさんの音声サンプル → 参考文献/謝辞

Per model the page now shows, in order: waveform, CH1, CH2, stereo, transcript,
and the GPT-4o rationale.  The rationale is read from the sample's own
rating.json rather than from samples.json, so the page cannot drift from the
artefact that produced the score.

The CSS block, the 18-noise list, the references and the footer are lifted from
the existing file unchanged; only the ordering and the sample section are new.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "projects" / "fdb-exp" / "Full-Duplex-Bench" / "v1_v1.5"
TASK = "synthetic_user_interruption"

# (key, name, colour, colour on a dark background) — the plain blue and green
# lose too much contrast against the dark theme's card.
MODELS = [("moshi", "Moshi", "#2CA02C", "#5FD183"),
          ("personaplex", "PersonaPlex", "#FF7F0E", "#FFAB52"),
          ("freezeomni", "Freeze-Omni", "#1F77B4", "#68AFE3")]
CONDITIONS = [
    ("clean", "雑音なし（clean）", None,
     "雑音がなければ 3 モデルとも割り込み後の話題に答えることができ、いずれも 5 点（満点）。"),
    ("tcar", "TCAR 0 dB", "0.000",
     "音量は音声と同じでも、エネルギーがほぼ 100 Hz 未満の低域うなりなので"
     "狭帯域はほとんど埋まらず、3 モデルとも 5 点のまま。"),
    ("omeeting", "OMEETING 0 dB", "0.457",
     "同じ 0 dB でも周囲の話し声が狭帯域を占めるため、3 モデルとも 0 点に崩れる。"),
]
# Held here rather than scraped out of the page: the table of contents also
# uses an <ol>, and scraping picked up its closing tag instead.
REFS = '''<ol class="refs">
  <li>X. Wang et al., Proc. ICML, 2025.</li>
  <li>A. Défossez et al., arXiv:2410.00037, 2024.</li>
  <li>R. Roy et al., Proc. ICASSP, 2026.</li>
  <li>G.-T. Lin et al., Proc. ASRU, 2025.</li>
  <li>J. Thiemann et al., Proc. Meetings on Acoustics, 2013.</li>
  <li>ITU-T Rec. P.56, 2011.</li>
  <li>ITU-T Rec. G.712, 2001.</li>
</ol>'''

SCOPE_TASKS = [
    ("pause", "Pause Handling", "ユーザのターンで黙っていられるか（TOR は低いほど良い）"),
    ("backchannel", "Backchanneling", "相槌を入れられるか（TOR ↓ / 頻度 ↑ / JSD ↓）"),
    ("smooth", "Smooth Turn Taking", "スムーズにターンテイクできるか（TOR ↑ / 遅延 ↓）"),
    ("interruption", "User Interruption", "割り込みに適切に反応できるか（TOR ↑ / 遅延 ↓ / GPT-4o ↑）"),
]

TOC = [
    ("poster", "ポスター"),
    ("samples", "音声サンプル 1（まずは 3 つだけ）"),
    ("noises", "DEMAND の環境音デモ"),
    ("scope", "今回スコープ外になったグラフ"),
    ("limits", "評価指標の限界"),
    ("samples2", "音声サンプル 2（もっとたくさん）"),
    ("refs", "参考文献・謝辞"),
]

# Sample set 2, in two groups: one noise type across every SNR, then the noise
# types set 1 had no room for. (key, heading, band ratio)
SIMPLE_SNR = [
    ("pcafeter_m5", "PCAFETER −5 dB", "0.361"),
    ("pcafeter_0", "PCAFETER 0 dB", "0.361"),
    ("pcafeter_5", "PCAFETER +5 dB", "0.361"),
    ("pcafeter_10", "PCAFETER +10 dB", "0.361"),
    ("pcafeter_15", "PCAFETER +15 dB", "0.361"),
    ("pcafeter_20", "PCAFETER +20 dB", "0.361"),
]
SIMPLE_NOISE = [
    ("dkitchen", "DKITCHEN 0 dB", "0.044"),
    ("npark", "NPARK 0 dB", "0.084"),
    ("scafe", "SCAFE 0 dB", "0.131"),
    ("pstation", "PSTATION 0 dB", "0.216"),
    ("presto", "PRESTO 0 dB", "0.663"),
]


def sample_dir(model: str, cond: str, sample_id: str) -> Path:
    base = ROOT / f"dataset_{model}"
    if cond == "clean":
        return base / "v1_0_clean" / TASK / sample_id
    return base / f"v1_0_noisy_{cond}" / TASK / "snr_0" / sample_id


def build_samples(meta: dict) -> str:
    sample_id = meta["sample_id"]
    transcripts = {(c["key"], m["key"]): m["text"]
                   for c in meta["conditions"] for m in c["models"]}
    out = []
    for cond, label, ratio, caption in CONDITIONS:
        head = f'<h3>{html.escape(label)}</h3>'
        if ratio is not None:
            head += f'<span class="ratio">狭帯域パワー占有率 {ratio}</span>'
        # Summary above the model blocks: at the bottom it sat after three
        # players and three transcripts, where nobody reads it.
        out.append(f'<section class="cond">\n  <header>{head}</header>\n  <div class="body">'
                   f'\n    <p class="cap">{caption}</p>')
        for key, name, colour, dark in MODELS:
            directory = sample_dir(key, cond, sample_id)
            rating = json.loads((directory / "rating.json").read_text())
            score, why = int(rating["rating"]), rating["analysis"].strip()
            good = "good" if score >= 3 else "bad"
            text = html.escape(transcripts[(cond, key)])
            out.append(f'''    <div class="track model" style="--mc:{colour};--mcd:{dark}">
      <p class="label"><span class="dot" style="background:{colour}"></span><span class="name">{name}</span><span class="score {good}">GPT-4o {score} 点</span></p>
      <div class="wave"><a href="figures/wave_{cond}_{key}.png"><img loading="lazy" src="figures/wave_{cond}_{key}.png" alt="{html.escape(label)} における {name} の波形"></a></div>
      <div class="players">
        <label>CH1　入力音声<audio controls preload="none" src="audio/{cond}_input.mp3"></audio></label>
        <label>CH2　{name} の応答<audio controls preload="none" src="audio/{cond}_{key}.mp3"></audio></label>
        <label>Stereo（左 CH1 ／ 右 CH2）<audio controls preload="none" src="audio/{cond}_{key}_stereo.mp3"></audio></label>
      </div>
      <p class="tr-label">User Interruption 後と判定されたモデル音声の ASR 書き起こし（GPT-4o Score の判定対象）</p>
      <p class="transcript">{text}</p>
      <p class="analysis"><span class="who">GPT-4o が出力した判断根拠</span>{html.escape(why)}</p>
    </div>''')
        out.append('  </div>\n</section>')
    return "\n".join(out)


def sample2_dir(model: str, key: str) -> Path:
    """Sample set 2 keys carry their own SNR, e.g. pcafeter_m5."""
    if "_" in key:
        noise, tag = key.rsplit("_", 1)
    else:
        noise, tag = key, "0"
    return ROOT / f"dataset_{model}" / f"v1_0_noisy_{noise}" / TASK / f"snr_{tag}" / "103"


def build_samples2(group, shared_ratio: str | None = None) -> str:
    """One section per model, its conditions listed inside in order.

    `shared_ratio` is for the SNR sweep, where every condition is the same noise
    type: the band ratio is stated once in the section header rather than
    repeated on all six rows.
    """
    out = []
    for model, name, colour, dark in MODELS:
        ratio_tag = (f'<span class="ratio">狭帯域パワー占有率 {shared_ratio}</span>'
                     if shared_ratio else "")
        out.append(f'<section class="cond" style="--mc:{colour};--mcd:{dark}">\n'
                   f'  <header><h3><span class="dot" style="background:{colour}"></span>'
                   f'<span class="name">{name}</span></h3>{ratio_tag}</header>'
                   f'\n  <div class="body">')
        for key, label, ratio in group:
            directory = sample2_dir(model, key)
            rating_path = directory / "rating.json"
            if rating_path.is_file():
                rating = json.loads(rating_path.read_text())
                score, why = int(rating["rating"]), rating["analysis"].strip()
                badge = f'<span class="score {"good" if score >= 3 else "bad"}">GPT-4o {score} 点</span>'
                reason = ('<p class="analysis"><span class="who">GPT-4o が出力した判断根拠</span>'
                          f'{html.escape(why)}</p>')
            else:
                # No rating.json means the benchmark scored TO = 0 and never sent
                # the sample to the judge.
                badge = '<span class="score none">GPT-4o 採点対象外</span>'
                reason = ('<p class="analysis"><span class="who">GPT-4o が出力した判断根拠</span>'
                          'TO = 0 と判定されたため採点対象外。</p>')
            per_row = "" if shared_ratio else f'<span class="ratio">占有率 {ratio}</span>'
            text = html.escape(json.loads((directory / "output.json").read_text())["text"].strip())
            out.append(f'''    <div class="track model">
      <p class="label"><span class="cname">{html.escape(label)}</span>{per_row}{badge}</p>
      <div class="wave"><a href="figures/wave_{key}_{model}.png"><img loading="lazy" src="figures/wave_{key}_{model}.png" alt="{html.escape(label)} における {name} の波形"></a></div>
      <div class="players">
        <label>CH1　入力音声<audio controls preload="none" src="audio/{key}_input.mp3"></audio></label>
        <label>CH2　{name} の応答<audio controls preload="none" src="audio/{key}_{model}.mp3"></audio></label>
        <label>Stereo（左 CH1 ／ 右 CH2）<audio controls preload="none" src="audio/{key}_{model}_stereo.mp3"></audio></label>
      </div>
      <p class="tr-label">User Interruption 後と判定されたモデル音声の ASR 書き起こし（GPT-4o Score の判定対象）</p>
      <p class="transcript">{text}</p>
      {reason}
    </div>''')
        out.append('  </div>\n</section>')
    return "\n".join(out)


def build_scope() -> str:
    out = []
    for key, title, blurb in SCOPE_TASKS:
        out.append(f"""<h3>{title}</h3>
<p class="cap">{blurb}</p>
<figure><a href="figures/scope_{key}.png"><img loading="lazy" src="figures/scope_{key}.png" alt="{title} の指標（18 種平均）"></a></figure>
<p class="cap">18 種類の雑音を平均した結果。破線と右端 clean 位置の点は、雑音なしのときの値。</p>
<details>
  <summary>雑音ごとの詳細（タップで開く）</summary>
  <div class="wide"><a href="figures/scope_{key}_detail_large.png"><img loading="lazy" src="figures/scope_{key}_detail.png" alt="{title} の雑音種類別の結果"></a></div>
  <p class="cap">18 種類を 1 列ずつ並べたシート。横にスクロールできます。図をタップすると高解像度で開きます。</p>
</details>""")
    return "\n".join(out)


def main() -> None:
    text = Path("index.html").read_text()
    meta = json.loads(Path("samples.json").read_text())

    css = text[text.index("<style>"):text.index("</style>") + len("</style>")]
    # Idempotent: the block runs from the first noise card to whatever heading
    # follows it, so re-running against an already-rebuilt page still works.
    noise_start = text.index('<div class="noise">')
    noises = text[noise_start:text.index("<h2", noise_start)].rstrip()
    footer = text[text.index("<footer>"):text.index("</footer>") + len("</footer>")]

    start, end = meta["interrupt_time"]
    toc = "\n".join(f'    <li><a href="#{i}">{html.escape(t)}</a></li>' for i, t in TOC)

    page = f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Full-Duplex音声対話システムの雑音頑健性評価 | YANS 2026 S5-P12</title>
<meta name="description" content="YANS 2026 ポスター発表 S5-P12 の音声サンプルと図表。">
<meta name="robots" content="noindex">
{css}
</head>
<body>
<header class="hero">
  <div class="inner">
    <p class="venue">YANS 2026　ポスター発表 S5-P12</p>
    <h1>Full-Duplex音声対話システムの雑音頑健性評価</h1>
    <p class="authors">中野 隼輔, 中田 亘, 齋藤 佑樹, 猿渡 洋</p>
    <p class="affil">東京大学</p>
  </div>
</header>

<div class="wrap">

<nav class="toc" aria-label="目次">
  <p class="toc-title">目次</p>
  <ol>
{toc}
  </ol>
</nav>

<h2 id="poster">ポスター</h2>
<figure><a href="poster.png"><img src="poster.png" alt="ポスター全体"></a></figure>
<p class="cap">タップで拡大表示できます。</p>
<p><a class="btn" href="poster.pdf">ポスターPDFをダウンロード</a></p>

<h2 id="samples">音声サンプル 1（まずは 3 つだけ）</h2>
<p class="cap">Full-Duplex-Bench<sup>[4]</sup> の <strong>User Interruption</strong> タスクの 1 例。
ユーザが 4.2〜7.4 秒に「{html.escape(meta["context"])}」と質問し、
それに<strong>モデルが応答している最中</strong>の 15.1〜17.3 秒に、
ユーザが「{html.escape(meta["interrupt"])}」と<strong>別の話題で割り込みます</strong>。
モデルは<strong>割り込み後の話題に答え直すのが正解</strong>です。
<strong>雑音なし（clean）と雑音 2 種（SNR 0 dB）</strong>の 3 条件を並べます。
雑音 2 種は大きさが同じで、変えているのは種類だけです。</p>

{build_samples(meta)}

<h2 id="noises">DEMAND の環境音デモ</h2>
<p class="cap">実験に使った DEMAND<sup>[5]</sup> の 18 種類の雑音を 10 秒ずつ。
<strong>全体パワーに対する狭帯域（300〜3400 Hz）パワー占有率</strong>が小さい順に並べています。
名前の頭文字は DEMAND のカテゴリで、
D: Domestic ／ N: Nature ／ O: Office ／ P: Public ／ S: Street ／ T: Transportation です。
RMS を揃え、モデルへの入力と同じ 24 kHz で書き出しています。</p>

{noises}

<h2 id="scope">今回スコープ外になったグラフ</h2>
<p class="cap">Full-Duplex-Bench の 4 タスクすべてを、同じ 18 種類 × 6 SNR で計測した結果です。
TOR・Latency・Frequency・JSD は下記「評価指標の限界」の理由で条件間の比較には使えないと判断し、
ポスターからは外しました。検証できるようすべて掲載します。
指標の定義はポスターと同じ（local 基準＋応答遅延 2 秒上限）です。</p>

{build_scope()}

<h2 id="limits">評価指標の限界</h2>
<p class="cap">今回用いた Full-Duplex-Bench が提案した指標には、いくつか判定の落とし穴があります。
ポスター右側で詳しく述べています。</p>
<ul class="limits">
  <li><strong>TOR</strong>：出力音声<strong>全体</strong>を 1 区間として「1 秒以上または 2 語以上」で判定するため、
    どこか 1 箇所でも喋れば TO = 1 になる。
    <strong>Backchanneling</strong> では、TO = 0 である出力音声しか分析対象にならないため、
    実際の挙動の分析とは言えない。
    <strong>Pause Handling</strong> では、相槌だけを 2 回返した応答も TO = 1 と数えられてしまう。</li>
  <li><strong>Latency</strong>：実際は Latency = 0.060 秒ほど（聞いた感じはほぼ 0 秒）のサンプルだったとしても、
    Full-Duplex-Bench では Latency = 0.240 秒 と計算されてしまうことがある。
    これは Latency の計算が<strong>アノテーションの質や ASR・VAD の性能に大きく依存している</strong>ためであり、
    間やテンポが重要な音声対話の分析においては問題がある。</li>
  <li><strong>GPT-4o Score</strong>：割り込み前から続いている発話も採点テキストに含まれるため、
    本来評価すべき「割り込みへの応答」だけを見ているとは限らない。</li>
</ul>

<h2 id="samples2">音声サンプル 2（もっとたくさん）</h2>
<p class="cap">音声サンプル 1 と同じ対話・同じ構成です。まず雑音の種類を PCAFETER に固定して
SNR を変えたもの、続いて音声サンプル 1 に載せられなかった雑音の種類（いずれも SNR 0 dB）。
どちらも<strong>モデルごとにまとめて</strong>並べています。</p>

<h3>SNR による変化（雑音は PCAFETER で固定）</h3>
{build_samples2(SIMPLE_SNR, shared_ratio="0.361")}

<h3>雑音の種類による変化（いずれも SNR 0 dB）</h3>
{build_samples2(SIMPLE_NOISE)}

<h2 id="refs">参考文献・謝辞</h2>
{REFS}
<p class="cap">本研究は、JST ムーンショット型研究開発事業 JPMJMS2011 および
JSPS 科研費 26H02531 の支援を受けて実施しました。</p>

{footer}

</div>
</body>
</html>
'''
    Path("index.html").write_text(page)
    print(f"index.html を再構成（{len(page.splitlines())} 行）")


if __name__ == "__main__":
    main()
