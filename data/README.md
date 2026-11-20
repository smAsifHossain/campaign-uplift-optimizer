# Data directory

Raw and processed data are intentionally excluded from Git.

Run the acquisition command from the repository root:

```bash
python -m campaign_uplift acquire
```

The command downloads the corrected Criteo Uplift v2.1 archive from Criteo's official Hugging
Face organization into `data/raw/`. The URL is pinned to a publisher commit. Acquisition validates
the expected byte size, SHA-256 checksum, gzip archive, and schema, then writes local provenance
metadata. See [`DATA_LICENSE.md`](../DATA_LICENSE.md) before using the dataset.

Synthetic data exist only in `campaign_uplift.synthetic` for tests and explicitly labeled
development runs. The production pipeline never silently substitutes synthetic observations
when acquisition fails.
