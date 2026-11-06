---
tags:
  - homelab
  - adr
  - observability
  - mimir
  - qnap
type: adr
status: accepted
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-06
adr: 56
---

# ADR-0056 - No-compact marks for Mimir blocks with checksum mismatches

## Status

Accepted on 2026-11-06. The follow-up decision on the deletion delay is open (see "Open").

## Context

After [[ADR-0054 - Decommission dockerhost]] the Mimir compactor (`grafana/mimir:3.2.1`, bucket `mimir-metrics` on the QNAP S3 `https://qnap.4jp.de:8443`, prefix `blocks/anonymous/`) failed repeatedly on merge jobs with `cannot populate chunk <ref> from block <ulid>: checksum mismatch`. A failing job aborts the whole compaction cycle, so every group behind it waited. Queries kept working.

## Evidence

Measured on 2026-11-06. Objects were downloaded with `aws s3api get-object` (twice for the first two blocks; both copies had the same SHA-256) and checked locally.

- **ETag calibration.** QNAP's multipart ETag for the `index` of `01M6P096JQ…` (2 parts) equals md5-of-md5s over 16 MiB parts (`bd16025f65a0ed70c1328eaa668d2465-2`), so this scheme is valid for the bucket.
- **Chunk CRC.** A chunk is `uvarint len | encoding | data | CRC32-Castagnoli(encoding+data)`. For both logged chunk refs the locally computed CRC equals the `actual` value in the compactor log (`935f9961`, `a5b8ca1c`): the compactor read the same bytes the bucket serves now.
- **Zero-filled part.** In every damaged block exactly one aligned 16 MiB part of `chunks/000001` is only `0x00` bytes. Chunks that start in or run into that part have a stored CRC of `00000000` (log: `expected:0`). In `01M6P096JQ…` the logged chunk (3735522) lies outside the zero part: it and the next chunk fail their CRC, framing breaks, and a valid chunk starts again 183 bytes after the first.
- **ETag.** In every damaged block the ETag from upload differs from the md5-of-parts of the bytes served now; undamaged blocks match.
- **Scan.** All `index` and `chunks/*` objects under `blocks/anonymous/` (about 1300 objects, 104 GB) were streamed and checked (ETag per 16 MiB part plus zero-part detection). Siblings of both groups (`01M5A78HXC…`, `01M6PKZ0XM…`, `01M6PAEFWV…`) are clean (ETag match, every chunk CRC OK). Limit: the listing was taken twice (a hung read forced a restart), so an object whose position shifted between the listings may be unchecked; the compactor log is the ongoing check. Objects created after about 15:00Z were not scanned.

|Block|Level|Zero part (16 MiB index)|Uploaded (UTC)|Parents|
|---|---|---|---|---|
|`01M519WTC7NZ5YPRAFMK4VYS5W`|4|17|2026-10-16 02:53|gone|
|`01M5BGNMPAW9R2TE304YZ8GBYQ`|3|7|2026-10-20 02:01|gone|
|`01M5E1SG0FEBW1C95ANEK7J98H`|4|1|2026-10-21 01:39|gone|
|`01M5K90EEE3FNR3ZDTV56SZXFR`|4|13|2026-10-23 02:28|gone|
|`01M6P096JQJ3NBC0V9F39Z8PJD`|3|1|2026-11-05 14:02|gone|
|`01M6RNKNT41CB104GG9N1VCSVZ`|5|16|2026-11-06 14:53|still present, were marked for deletion|

All are compactor-written (`thanos.source=compactor`). Logged errors: `01M519WTC7…` chunk 268435453 (the 2026-10-15 group), `01M5BGNMPA…` chunk 117440411 (2026-10-19 group), `01M6P096JQ…` chunk 3735522 (2026-11-05 group); the other three were found by the scan.

**The damage is not historical.** The sixth block was written 35 minutes after the first marks, so compactor uploads to the QNAP S3 still produce damaged chunk files now (6 of the large compactor-written chunk files in the bucket). Where the damage arises is open. Raw facts: the QNAP syslog in Loki has no line within ±30 min of the 2026-10-20 02:01Z and 2026-11-05 14:02Z uploads; `qnap` node-exporter shows `up=1` and all `md*` arrays `active=6 failed=0` in those windows; the QNAP UI reports good health for all disks (user); QuObjects was updated from 2.5.869 to 2.5.1289 on 2026-11-03 03:38Z, so it cannot explain the 2026-10-16 to 2026-10-23 blocks; `k0s0` exports no EDAC metrics; `aws s3 cp` (multipart ranged GET) on the large chunk files failed with `InternalError` while a plain `GET` and `s3api get-object --range` worked.

**Data loss already happened** for the five blocks whose parents are gone: the compactor deleted the source blocks `deletion_delay: 2h` after the merge, so the zero-filled 16 MiB part (and in `01M6P096JQ…` 183 bytes) is not recoverable from the bucket. [INFERENCE] Series that only the legacy Prometheus scraped could be restored from the raw TSDB tarball in `backups/dockerhost/host/` (ADR-0054, covers up to 2026-11-05 19:00 UTC; not tested); series scraped by Alloy exist only in Mimir.

## Decision

- Mark each confirmed block with a **no-compact** mark (`mimirtool blocks mark --mark-type no-compact --tenant anonymous --storage-prefix blocks`). It writes `anonymous/<ulid>/no-compact-mark.json` and `anonymous/markers/<ulid>-no-compact-mark.json`; the compactor skips the block and the other groups continue. Details string: `zero-filled 16 MiB part <n> in chunks/000001, ETag mismatch, ADR-0056` (first two: `checksum mismatch in chunk <ref>, ADR-0056`).
- Remove the deletion marks of the three parents of `01M6RNKNT4…` (`01M6PKYZKWWTDRR2TKTAXXSTMY`, `01M6PKYY5KDCPV7CBJQ8WD3TRE`, `01M6MQ1EGBH681GQX3VPTPN812`, marked about 14:53Z, deletion due about 16:53Z) with `mimirtool blocks mark --mark-type deletion --remove`, so their data survives. The compactor will merge them again into a new block.
- Do not delete, rewrite or repair any damaged block object.
- A block is confirmed when its ETag mismatches **and** its chunk file has a zero-filled aligned part or the CRC of a logged chunk fails.

## Also decided

- Raise `compactor.deletion_delay` from `2h` (chart default) to `48h` (`MIMIR_COMPACTOR_DELETION_DELAY` in `services/observability/observability/mimir.py`, user decision 2026-11-06). Merged-away blocks then survive 48 h, enough time to notice a damaged merge result and restore its parents. Cost: about two extra days of source blocks in the bucket. Rollback: set the value back to `2h`.

## Open

- `01M6RNKNT4…`: its parents were marked for deletion again at 15:48Z because the damaged block covers them. At 16:09Z the block got a deletion mark (due after the 48 h delay; remove the mark to undo) and the parents' deletion marks were removed again, so the compactor can merge the three parents anew. Check the new level-5 result (per-part md5 against the ETag) before the parents' next deletion.
- Root cause on the QNAP side; options if the pattern continues: change the S3 part size/concurrency of the Mimir client, move the Mimir bucket off QuObjects, or verify each merge result before its parents are deleted.

## Consequences

- Marked blocks are never merged further and stay as small blocks until retention (400 days) removes them. Chunks in a zero-filled part have no samples. `count(up)` at 2026-11-05T06:00Z, 2026-10-19T18:00Z, 2026-10-15T12:00Z and 2026-10-20T12:00Z returned data (99, 121, 85, 121 series), and range queries of `up` over each damaged block's window succeeded. **But the damage is wider than the zero part:** a range query of `cnpg_collector_last_available_backup_timestamp{pod="tandoor-db-1"}` over 2026-10-29 to 2026-11-06 failed with `unsupported chunk encoding 225` at offset 12896089 of `01M6P096JQ…` (part 0). Series whose chunks sit in damaged bytes make the whole query fail; narrow the range to avoid the block (for example start after 2026-11-05T12:00Z) until the block's fate is decided.
- Verified after marking: no `checksum mismatch` in the compactor log for 40 minutes, the compactor merges the other groups again.

## Rollback

Delete both marker objects of a block (`anonymous/<ulid>/no-compact-mark.json`, `anonymous/markers/<ulid>-no-compact-mark.json`) or run `mimirtool blocks mark --mark-type no-compact … --remove`. The compactor then tries the block again (and fails again while the damage exists).

## Related

- [[ADR-0054 - Decommission dockerhost]]
- [[ADR-0057 - No off-site copy of the dockerhost archive and Mimir history]]
- [[ADR-0019 - LGTM observability stack on k0s]]
