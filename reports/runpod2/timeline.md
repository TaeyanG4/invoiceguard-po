| KST | UTC | event | until next event | source |
|---|---|---|---:|---|
| 20:49:38 | 11:49:38 | Pod created (create-pod, L40S EUR-IS-2) | 5m 06s | manual |
| 20:54:44 | 11:54:44 | setup done: venvs + 2B model, SHA256 ok (setup2.log mtime) | 0m 08s | manual |
| 20:54:52 | 11:54:52 | teacher download (background) | 0m 00s | run2.log |
| 20:54:52 | 11:54:52 | merge on Pod (parity with the local merge) | 0m 27s | run2.log |
| 20:55:19 | 11:55:19 | merge exit=0 | 2m 26s | run2.log |
| 20:57:45 | 11:57:45 | healthy m0_bf16 | 2m 41s | run2.log |
| 21:00:26 | 12:00:26 | bench vllm_run2_m0_bf16 exit=0 | 1m 10s | run2.log |
| 21:01:36 | 12:01:36 | healthy m1merged_bf16 | 1m 48s | run2.log |
| 21:03:24 | 12:03:24 | bench vllm_run2_m1merged_bf16 exit=0 | 1m 50s | run2.log |
| 21:05:14 | 12:05:14 | healthy m1merged_fp8 | 1m 24s | run2.log |
| 21:06:38 | 12:06:38 | bench vllm_run2_m1merged_fp8 exit=0 | 1m 16s | run2.log |
| 21:07:54 | 12:07:54 | healthy m0_fp8 | 1m 55s | run2.log |
| 21:09:49 | 12:09:49 | bench vllm_run2_m0_fp8 exit=0 | 1m 06s | run2.log |
| 21:10:55 | 12:10:55 | healthy m1merged_bf16_seqs4 | 1m 57s | run2.log |
| 21:12:52 | 12:12:52 | bench vllm_run2_m1merged_bf16_seqs4 exit=0 | 0m 15s | run2.log |
| 21:13:07 | 12:13:07 | wait for teacher download | 0m 00s | run2.log |
| 21:13:07 | 12:13:07 | download exit=0 | 2m 51s | run2.log |
| 21:15:58 | 12:15:58 | 32B teacher attempt 1 failed: KV cache 0.47 GiB (log mtime) | 2m 32s | manual |
| 21:18:30 | 12:18:30 | 32B teacher attempt 2 started (run2 queue stopped) | 1m 44s | manual |
| 21:20:14 | 12:20:14 | 32B teacher attempt 2 failed: ninja not on PATH (log mtime) | 0m 30s | manual |
| 21:20:44 | 12:20:44 | shards (public train/dev images) | 0m 20s | p14.log |
| 21:21:04 | 12:21:04 | fetch exit=0 | 0m 00s | p14.log |
| 21:21:04 | 12:21:04 | P14 train (bf16 base, plain LoRA) | 8m 16s | p14.log |
| 21:29:20 | 12:29:20 | train exit=0 | 11m 04s | p14.log |
| 21:40:24 | 12:40:24 | dev44_l40s_m0_bf16 exit=0 | 9m 15s | p14.log |
| 21:49:39 | 12:49:39 | dev44_l40s_m1_nf4 exit=0 | 5m 52s | p14.log |
| 21:55:31 | 12:55:31 | dev44_l40s_m1_bf16lora exit=0 | 0m 01s | p14.log |
| 21:55:32 | 12:55:32 | P14_DONE | 2m 21s | p14.log |
| 21:57:53 | 12:57:53 | teacher healthy | 4m 57s | teacher_run.log |
| 22:02:50 | 13:02:50 | 32B stopped after 2 drafts (15 tok/s); 8B teacher started | 0m 08s | manual |
| 22:02:58 | 13:02:58 | teacher8b revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b | 0m 12s | teacher8b_run.log |
| 22:03:10 | 13:03:10 | downloaded | 1m 46s | teacher8b_run.log |
| 22:04:56 | 13:04:56 | teacher8b healthy | 15m 14s | teacher8b_run.log |
| 22:20:10 | 13:20:10 | teacher8b_label exit=0 | 0m 08s | teacher8b_run.log |
| 22:20:18 | 13:20:18 | TEACHER8B_DONE | 1m 12s | teacher8b_run.log |
| 22:21:30 | 13:21:30 | backup packed and verified (62 files) | 1m 28s | manual |
| 22:22:58 | 13:22:58 | Pod deleted (delete-pod 204), list-pods 0 |  | manual |

First to last event: 1h 33m 20s.
