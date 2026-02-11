# ICA: Information-Aware Credit Assignment for Visually Grounded Long-Horizon Information-Seeking Agents

<div align="center">
  <a href="https://arxiv.org/abs/xxxx.xxxxx">📄 Paper</a> |
  <a href="https://huggingface.co/collections/yyj1659748497/ica-dataset">🤗 Datasets</a> |
  <a href="https://huggingface.co/collections/yyj1659748497/ica">🤗 Models</a>
</div>

## News & Updates
code is coming soon

## introduction

<img width="1486" height="664" alt="pipeline" src="https://github.com/user-attachments/assets/184625b6-ee4a-4bec-a01f-e3b5f3e4b86a" />


## Results Showcase

<div align="center">


| Model / Framework | Tools | BrowseComp | GAIA | Xbench-DS | Seal-0 |
|---|---|---:|---:|---:|---:|
| **Proprietary Agents** |  |  |  |  |  |
| Claude-4-Sonnet\* | – | 12.2 | 68.3 | 64.6 | – |
| OpenAI-o3\* | – | 49.7 | 70.5 | 66.7 | 18.9 |
| OpenAI DeepResearch\* | – | 51.5 | 67.4 | – | – |
| **Open-Source Agents (<15B)** |  |  |  |  |  |
| WebExplorer-8B\* | Search & Fetch (text) | **15.7** | 50.0 | 53.7 | – |
| WebSailor-7B\* | Search & Fetch (text) | 6.7 | – | 34.3 | – |
| DeepDive-9B\* | Search & Fetch (text) | 6.3 | – | 38.0 | 12.2 |
| MiroThinker-14B-DPO-v0.1\* | Search & Fetch (text) | 9.0 | – | 30.0 | – |
| Qwen3-14B\* | Search & Fetch (text) | 1.0 | – | 20.0 | – |
| InfoAgent\* | Search & Fetch (text) | 15.3 | – | 40.4 | – |
| Qwen3-VL-8B-ICA (Ours) | Search & Fetch (snap.) | 13.1 | **61.2** | **58.0** | **22.5** |
| **Open-Source Agents (>15B)** |  |  |  |  |  |
| ASearcher-Web-32B\* | Search & Fetch (text) | 5.2 | 52.8 | 42.1 | – |
| DeepDive-V2-38B\* | Search & Fetch (text) | 13.4 | – | 53.0 | – |
| MiroThinker-32B-DPO-v0.2\* | Search & Fetch (text) | 13.0 | 64.1 | – | – |
| Kimi-K2-Instruct-1T\* | Search & Fetch (text) | 14.1 | 57.7 | 50.0 | – |
| WebDancer-QwQ-32B\* | Search & Fetch (text) | 3.8 | 51.5 | 38.3 | – |
| WebSailor-32B\* | Search & Fetch (text) | 10.5 | 53.2 | 53.3 | 21.3 |
| DeepDive-32B\* | Search & Fetch (text) | 15.3 | – | 51.8 | 25.5 |
| C-GRPO\* | Search & Fetch (text) | **24.8** | 56.3 | 57.7 | – |
| WebShaper-QwQ-32B\* | Search & Fetch (text) | – | 53.3 | 35.0 | – |
| Qwen3-VL-30B-A3B-ICA (Ours) | Search & Fetch (snap.) | 17.1 | **65.0** | **75.0** | **27.0** |

**Comparison of different models on information-seeking benchmarks.**
</div>


| Stage | Method | BC-100 | GAIA | XDS | Seal-0 |
|---|---|---:|---:|---:|---:|
| **Baseline: Qwen3-VL-8B-Thinking** |  |  |  |  |  |
| Baseline | Base - RAG | 1.0 | 29.1 | 39.0 | 7.2 |
| SFT | SFT - RAG | 6.0 <span style="color: #1a7f37;">(+5.0)</span> | 47.1 <span style="color: #1a7f37;">(+18.0)</span> | 39.0 <span style="color: #1a7f37;">(+0.0)</span> | 18.0 <span style="color: #1a7f37;">(+10.8)</span> |
| SFT | SFT - Snap. | 6.0 <span style="color: #1a7f37;">(+5.0)</span> | 49.5 <span style="color: #1a7f37;">(+20.4)</span> | 44.0 <span style="color: #1a7f37;">(+5.0)</span> | 19.1 <span style="color: #1a7f37;">(+11.9)</span> |
| RL | GRPO - Snap. | 7.0 <span style="color: #1a7f37;">(+6.0)</span> | 51.7 <span style="color: #1a7f37;">(+22.6)</span> | 54.0 <span style="color: #1a7f37;">(+15.0)</span> | 20.7 <span style="color: #1a7f37;">(+13.5)</span> |
| RL | ICA - Snap. | 13.0 <span style="color: #1a7f37;">(+12.0)</span> | 57.3 <span style="color: #1a7f37;">(+28.2)</span> | 59.0 <span style="color: #1a7f37;">(+20.0)</span> | 22.5 <span style="color: #1a7f37;">(+15.3)</span> |
| **Baseline: Qwen3-VL-30B-A3B-Thinking** |  |  |  |  |  |
| Baseline | Base - RAG | 3.0 | 31.1 | 38.0 | 9.9 |
| SFT | SFT - RAG | 10.0 <span style="color: #1a7f37;">(+7.0)</span> | 57.3 <span style="color: #1a7f37;">(+26.2)</span> | 61.0 <span style="color: #1a7f37;">(+23.0)</span> | 22.5 <span style="color: #1a7f37;">(+12.6)</span> |
| SFT | SFT - Snap. | 11.0 <span style="color: #1a7f37;">(+8.0)</span> | 60.2 <span style="color: #1a7f37;">(+29.1)</span> | 64.0 <span style="color: #1a7f37;">(+26.0)</span> | 23.4 <span style="color: #1a7f37;">(+13.5)</span> |
| RL | GRPO - Snap. | 13.0 <span style="color: #1a7f37;">(+10.0)</span> | 57.3 <span style="color: #1a7f37;">(+26.2)</span> | 66.0 <span style="color: #1a7f37;">(+28.0)</span> | 24.3 <span style="color: #1a7f37;">(+14.4)</span> |
| RL | ICA - Snap. | 17.0 <span style="color: #1a7f37;">(+14.0)</span> | 65.0 <span style="color: #1a7f37;">(+33.9)</span> | 75.0 <span style="color: #1a7f37;">(+37.0)</span> | 27.0 <span style="color: #1a7f37;">(+17.1)</span> |


**Ablation Study on different components.**

