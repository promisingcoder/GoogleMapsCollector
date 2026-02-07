# Resuming Collections

> **Note:** Checkpoint/resume is a V2-only feature. The V1 collector (`collect()` / `gmaps-collect`) has no resume capability.

## How Checkpoints Work

During collection, V2 periodically saves its state to a checkpoint file:

```
output/.checkpoint_{category}_{area}.json
```

The checkpoint records:

- Which grid cells have been completed
- Which cells failed
- All collected `place_id` and `hex_id` values (for deduplication)
- Which businesses have been enriched
- Start time and last checkpoint time

## Auto-Resume

Resume is enabled by default (`resume=True`). When V2 starts, it checks for an existing checkpoint file. If one exists, it:

1. Loads the previous state
2. Skips already-completed cells
3. Continues from where it left off
4. Maintains deduplication across sessions

```
Resuming from checkpoint:
  Completed cells: 45
  Businesses collected: 312
```

## Force a Fresh Start

To ignore an existing checkpoint and start over:

**Python:**

```python
result = extractor.collect_v2("NYC", "lawyers", resume=False)
```

**CLI:**

```bash
gmaps-collect-v2 "NYC" "lawyers" --no-resume
```

## Checkpoint Interval

Checkpoints are saved every N businesses (default: 100). Adjust with `checkpoint_interval`:

```python
result = extractor.collect_v2("NYC", "lawyers", checkpoint_interval=50)
```

```bash
gmaps-collect-v2 "NYC" "lawyers" -c 50
```

## Checkpoint Cleanup

On successful completion with no failed cells, the checkpoint file is automatically deleted. If any cells failed, the checkpoint is preserved so you can resume later.

## KeyboardInterrupt

If you press Ctrl+C during a V2 CLI collection, the process prints:

```
Interrupted! Progress saved to checkpoint.
Run with --resume to continue from where you left off.
```

The state at the time of interruption is saved. Run the same command again (resume is on by default) to continue.

## Manual Checkpoint Cleanup

To force a reset without `--no-resume`, delete the checkpoint file:

```bash
rm output/.checkpoint_lawyers_manhattan.json
```
