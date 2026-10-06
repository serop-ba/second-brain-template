# Meta Ads (CSV export)

No API setup. Works from the export Ads Manager gives you.

1. Ads Manager, set the date range, **Breakdown: By day**, columns: *Amount spent*, *Impressions*, *Link clicks*, *Results*.
2. **Reports, Export, CSV**. Save the file into `automations/meta-ads/exports/`.
3. `python3 brain.py refresh meta-ads`

Run it again with a newer export any time: values are stored per day, so overlapping exports just overwrite the same days.

To get your own thresholds (for example a maximum cost per result), ask Claude: *"set healthy, watch and bad bands for cost per result from my price and margin"*.
