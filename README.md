# ICA: Information-Aware Credit Assignment for Visually Grounded Long-Horizon Information-Seeking Agents

[📄 Paper]| [🤗 Datasets](https://huggingface.co/collections/yyj1659748497/ica-dataset) | [🤗 Models]([https://huggingface.co/yyj1659748497/ICA-8B](https://huggingface.co/collections/yyj1659748497/ica))

## News & Updates:
---

## introduction
---
<img width="1486" height="664" alt="pipeline" src="https://github.com/user-attachments/assets/184625b6-ee4a-4bec-a01f-e3b5f3e4b86a" />

## Results Showcase

---
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
