# ICA: Information-Aware Credit Assignment for Visually Grounded Long-Horizon Information-Seeking Agents

<div align="center">
  <a href="https://arxiv.org/abs/xxxx.xxxxx"><img alt="arXiv Paper" src="https://img.shields.io/badge/arXiv-Paper-b31b1b?style=flat-square&logo=arxiv&logoColor=white"></a>
  <a href="https://huggingface.co/ICA-DeepResearch/datasets"><img alt="Hugging Face Datasets" src="https://img.shields.io/badge/Hugging%20Face-Datasets-ffbd59?style=flat-square&logo=huggingface&logoColor=white"></a>
  <a href="https://huggingface.co/ICA-DeepResearch/models"><img alt="Hugging Face Models" src="https://img.shields.io/badge/Hugging%20Face-Models-ffbd59?style=flat-square&logo=huggingface&logoColor=white"></a>
</div>

## News & Updates
2026-05-20: We have updated our paper, dataset and models!
2026-02-11: We have open-sourced the [paper](PASTE_PAPER_URL_HERE), [dataset](https://huggingface.co/ICA-DeepResearch/datasets), and [models](https://huggingface.co/ICA-DeepResearch/models)


## Introduction

We propose an evidence-centric framework for web agent learning that represents information acquired through tools as identifiable units for comparison across trajectories. In particular, **fetched webpages are represented as rendered snapshots**, preserving layout and multimodal content as stable content-level observations. Building on these units, we introduce **Information-Aware Credit Assignment**, a post hoc reward propagation method that estimates turn-level utility scores from rollout success rates and assigns **dense rewards** to intermediate steps that introduced high-utility information. Integrated with GSPO, our method consistently improves performance on BrowseComp, GAIA, Xbench-DS, and Seal-0.

### Highlights

- **Visual-native snapshots:** Preserve layout semantics (headings, tables, and regions) and capture visually grounded evidence (figures and charts).
- **Evidence-level credit assignment:** Estimates association-based utility scores for tool-acquired information and propagates dense rewards to the search and fetch turns that introduced it.
- **Consistent improvements:** Our 8B model outperforms most reported open-source agents under 15B parameters.

<img width="3618" height="1633" alt="pipeline" src="https://github.com/user-attachments/assets/eca7e1b0-a7b9-4c58-b2ac-d90320bf321a" />



## Results Showcase

<div align="center">

<p><b>Table 1:</b> Comparison of different models on information-seeking benchmarks. 

<table>
  <thead>
    <tr>
      <th align="left">Model / Framework</th>
      <th align="center">Tools</th>
      <th align="center">BrowseComp</th>
      <th align="center">GAIA</th>
      <th align="center">Xbench-DS</th>
      <th align="center">Seal-0</th>
    </tr>
  </thead>
  <tbody>
    <!-- Proprietary Agents -->
    <tr>
      <td colspan="6" align="left"><b><i>Proprietary Agents</i></b></td>
    </tr>
    <tr>
      <td align="left">Claude-4-Sonnet<sup>*</sup></td>
      <td align="center">--</td>
      <td align="center">12.2</td>
      <td align="center">68.3</td>
      <td align="center">64.6</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">OpenAI-o3<sup>*</sup></td>
      <td align="center">--</td>
      <td align="center">49.7</td>
      <td align="center">70.5</td>
      <td align="center">66.7</td>
      <td align="center">18.9</td>
    </tr>
    <tr>
      <td align="left">OpenAI DeepResearch<sup>*</sup></td>
      <td align="center">--</td>
      <td align="center">51.5</td>
      <td align="center">67.4</td>
      <td align="center">--</td>
      <td align="center">--</td>
    </tr>
    <!-- Open-Source Agents (<15B) -->
    <tr>
      <td colspan="6" align="left"><b><i>Open-Source Agents (&lt;15B)</i></b></td>
    </tr>
    <tr>
      <td align="left">WebExplorer-8B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center"><u>15.7</u></td>
      <td align="center"><u>50.0</u></td>
      <td align="center"><u>53.7</u></td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">WebSailor-7B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">6.7</td>
      <td align="center">--</td>
      <td align="center">34.3</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">DeepDive-9B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">6.3</td>
      <td align="center">--</td>
      <td align="center">38.0</td>
      <td align="center"><u>12.2</u></td>
    </tr>
    <tr>
      <td align="left">MiroThinker-14B-DPO-v0.1<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">9.0</td>
      <td align="center">--</td>
      <td align="center">30.0</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">Qwen3-14B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">1.0</td>
      <td align="center">--</td>
      <td align="center">20.0</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">InfoAgent<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">15.3</td>
      <td align="center">--</td>
      <td align="center">40.4</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left"><b>Qwen3-VL-8B-ICA (Ours)</b></td>
      <td align="center">Search & Fetch (snap.)</td>
      <td align="center"><b>25.0</b></td>
      <td align="center"><b>69.9</b></td>
      <td align="center"><b>71.0</b></td>
      <td align="center"><b>25.2</b></td>
    </tr>
    <!-- Open-Source Agents (>15B) -->
    <tr>
      <td colspan="6" align="left"><b><i>Open-Source Agents (&gt;15B)</i></b></td>
    </tr>
    <tr>
      <td align="left">ASearcher-Web-32B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">5.2</td>
      <td align="center">52.8</td>
      <td align="center">42.1</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">MiroThinker-32B-DPO-v0.2<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">13.0</td>
      <td align="center">64.1</td>
      <td align="center">--</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">Kimi-K2-Instruct-1T<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">14.1</td>
      <td align="center">57.7</td>
      <td align="center">50.0</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">WebDancer-QwQ-32B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">3.8</td>
      <td align="center">51.5</td>
      <td align="center">38.3</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">WebSailor-32B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">10.5</td>
      <td align="center">53.2</td>
      <td align="center">53.3</td>
      <td align="center">21.3</td>
    </tr>
    <tr>
      <td align="left">DeepDive-32B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">15.3</td>
      <td align="center">--</td>
      <td align="center">51.8</td>
      <td align="center">25.5</td>
    </tr>
    <tr>
      <td align="left">C-GSPO<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center"><u>24.8</u></td>
      <td align="center">56.3</td>
      <td align="center">57.7</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">WebShaper-QwQ-32B<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">--</td>
      <td align="center">53.3</td>
      <td align="center">35.0</td>
      <td align="center">--</td>
    </tr>
    <tr>
      <td align="left">WebLeaper<sup>*</sup></td>
      <td align="center">Search & Fetch (text)</td>
      <td align="center">22.7</td>
      <td align="center"><u>69.9</u></td>
      <td align="center"><u>62.3</u></td>
      <td align="center"><b>35.1</b></td>
    </tr>
    <tr>
      <td align="left"><b>Qwen3-VL-30B-A3B-ICA (Ours)</b></td>
      <td align="center">Search & Fetch (snap.)</td>
      <td align="center"><b>26.1</b></td>
      <td align="center"><b>72.8</b></td>
      <td align="center"><b>76.0</b></td>
      <td align="center"><u>27.0</u></td>
    </tr>
  </tbody>
</table>
</div>


**Table 2.** *Ablation study on different components.*

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

<!-- <table>
  <thead>
    <tr>
      <th align="left">Method</th>
      <th align="center">BC-100</th>
      <th align="center">GAIA</th>
      <th align="center">XDS</th>
      <th align="center">Seal-0</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td colspan="5" align="left"><b>Baseline: Qwen3-VL-8B-Thinking</b></td>
    </tr>
    <tr>
      <td align="left">Baseline - Text</td>
      <td align="center">1.0</td>
      <td align="center">29.1</td>
      <td align="center">39.0</td>
      <td align="center">7.2</td>
    </tr>
    <tr>
      <td align="left">SFT - Text</td>
      <td align="center">11.0 <sub>(+10.0)</sub></td>
      <td align="center">54.3 <sub>(+25.2)</sub></td>
      <td align="center">55.0 <sub>(+16.0)</sub></td>
      <td align="center">20.7 <sub>(+13.5)</sub></td>
    </tr>
    <tr>
      <td align="left">SFT - Snap.</td>
      <td align="center">18.0 <sub>(+17.0)</sub></td>
      <td align="center">56.4 <sub>(+27.3)</sub></td>
      <td align="center">66.0 <sub>(+27.0)</sub></td>
      <td align="center">23.4 <sub>(+16.2)</sub></td>
    </tr>
    <tr>
      <td align="left">GSPO - Snap.</td>
      <td align="center">22.0 <sub>(+21.0)</sub></td>
      <td align="center">60.2 <sub>(+31.1)</sub></td>
      <td align="center">68.0 <sub>(+29.0)</sub></td>
      <td align="center">24.3 <sub>(+17.1)</sub></td>
    </tr>
    <tr>
      <td align="left">ICA - Snap.</td>
      <td align="center">25.0 <sub>(+24.0)</sub></td>
      <td align="center">69.9 <sub>(+40.8)</sub></td>
      <td align="center">71.0 <sub>(+32.0)</sub></td>
      <td align="center">25.2 <sub>(+18.0)</sub></td>
    </tr>
  </tbody>
</table> -->


## Quick Start: Inference

### Prerequisites

- Python 3.10+
- A Serper API key (for web search) &mdash; set via `SERPER_API_KEY` in `run_inference.sh`

### 1. Serve the model

Start the model with vLLM (on a GPU node):

```bash
vllm serve /path/to/your/model \
  --served-model-name $MODEL_NAME \
  --tensor-parallel-size 4 \
  --dtype bfloat16 \
  --max-model-len 262144 \
  --max-num-batched-tokens 40960 \
  --max-num-seqs 32 \
  --limit-mm-per-prompt.images 999 \
  --limit-mm-per-prompt.video 0 \
  --mm-processor-cache-type shm \
  --host 0.0.0.0 \
  --port 8080
```

### 2. Run inference

Edit the top of `run_inference.sh` to point to your vLLM endpoint, then run:

```bash
# Configure in run_inference.sh:
#   VLLM_HOST=<your-vllm-host>
#   VLLM_PORT=<your-vllm-port>
#   VLLM_MODEL_NAME=<served-model-name>

bash run_inference.sh
```

Quick start command:

```bash
VLLM_HOST=10.0.0.1 VLLM_PORT=8080 CONCURRENCY=20 LIMIT=50 bash run_inference.sh
```

### 3. Output format

Each line in the output JSONL contains:

```json
{
  "id": 0,
  "question": "...",
  "answer": "...",
  "prediction": "model's final answer",
  "trajectory": [ ... ],
  "num_messages": 49,
  "elapsed_s": 123.4
}
```

- `trajectory`: Full multi-turn conversation history including all tool calls and responses
- `prediction`: The model's final answer after all search/fetch rounds

### Project Structure

```
ICA-MM-DeepSearch
├── inference.py          # Core inference logic (predict_qwen_search)
├── run_inference.py      # Batch runner with concurrent execution
├── run_inference.sh      # Entry point: env setup + launch
├── mcp/                  # MCP tools package (self-contained)
│   ├── mcp_tools/
│   │   ├── tools/
│   │   │   ├── serper.py         # Web search (Serper API)
│   │   │   └── fetch_to_img.py   # Page screenshot (Playwright)
│   │   ├── core/                 # MCP framework
│   │   └── config/               # Config loader
│   ├── pw_browsers/              # Bundled Playwright browsers
│   └── dist/                     # Pre-built wheels
├── models/                       # Model weights
└── data/                         # Input datasets
```
