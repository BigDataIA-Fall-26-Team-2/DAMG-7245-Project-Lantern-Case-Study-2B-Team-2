# Unit economics — deployed Case Study 2B

Inventory checked on **2026-10-30**, using AWS CLI profile `lantern`, region
`us-east-1`. These are resource-cost estimates, not an AWS invoice or a claim of
analyst savings. The pipeline parses published SEC tables; it uses **no Textract,
paid model inference, or per-document extraction API**.

## Actual provisioned resources

| Resource | Observed configuration | Budget rate | 730-hour month |
|---|---|---|---:|
| EC2 | One `m7i-flex.large`, Linux/shared, instance `i-089c6d5b3bfd4bd97`; 2 vCPU, 8 GiB RAM | $0.09576/running hour | $69.90 |
| EBS | One 40 GiB gp3 root volume; baseline 3,000 IOPS and 125 MiB/s | $0.08/GiB-month; no provisioned performance above baseline | $3.20 |
| Public IPv4 | One attached Elastic IP | $0.005/hour while allocated, including when EC2 is stopped | $3.65 |
| S3 | `lantern-team2-dvc-fall-2026/cs2b/`: 71 current objects, 755,618,206 bytes (0.704 GiB) | S3 Standard first-tier assumption, $0.023/GB-month (binary billing GB) | $0.02 |
| **Fixed baseline** | One server, disk, IP, and this project prefix only | Before variable charges, credits and tax | **$76.77/month** |

EC2 rate was verified from AWS's public regional price list: SKU
`SD5Q9AZVZ786UZA2`, effective `2026-10-01`, USD/hour, Linux, shared tenancy,
On-Demand. The authenticated Pricing API was denied; the public catalog supplied
this rate without changing IAM permissions. EBS and public-IP rates come from AWS
pricing pages. S3 assumes Standard storage; the count measures current objects,
not noncurrent versions or unfinished multipart uploads. Other prefixes, other
instances, snapshots, and account-wide services are outside this project estimate.

The 40 GiB disk is **allocated capacity**, not measured used disk space. RAM and
vCPU are provisioned capacity, not observed consumption. CloudWatch CPU access was
denied for the CLI identity; no CPU utilization, peak RAM, or EC2 runtime is
claimed here. DVC cache plus the checked-out data, dependencies, and scratch
copies consume additional local disk; use `df -h` and `du -sh .dvc/cache data outputs`
on EC2 to measure actual use before adding more releases.

## What operating the demo costs

| Scenario | Compute hours | IP/storage retention | Estimated cost |
|---|---:|---|---:|
| Always on, average month | 730 | 730 hours / full month | **$76.77/month** |
| 8 hours/day for 30 days | 240 | IP and storage retained for full 730-hour budget month | **$29.85/month** |
| Stopped all month | 0 | IP and storage retained | **$6.87/month** |
| One extra running hour | 1 | Existing storage already retained | **$0.10076** compute + public IPv4 |

Formula: `running_hours × 0.09576 + allocated_IP_hours × 0.005 + 40 × 0.08
+ stored_GiB × 0.023`. Storage is prorated when kept for only part of a month.
Stopping EC2 saves its compute charge; it does not delete the disk or release the
Elastic IP. These examples are gross list prices, before free-tier credits,
discounts, taxes, or support fees. EC2 Linux has a 60-second minimum and then
per-second billing; a short pipeline does not make an always-on server free.

Variable S3 budget: GET requests are $0.0004/1,000 and PUT/COPY/POST/LIST requests
$0.005/1,000 for Standard in this region. For illustration, 1,000 GETs plus 100
PUT/LISTs costs $0.0009. DVC can issue metadata checks and multiple requests per
object; 71 objects does not mean exactly 71 requests. Repeated versions increase
storage. Internet downloads and app traffic can add transfer charges; applicable
free transfer is account-wide. No traffic volume or free allowance is assumed in
the fixed baseline. EC2 and S3 are in the same region; this estimate does not
include a NAT gateway, load balancer, domain, or paid monitoring.

## Five-line task economics

For the handout, cost per task is reported per filing processed; cost per admitted
filing is an additional measure, not a manually verified investment decision. Current outputs: **177 attempted, 101
admitted, 76 excluded**, with **44.4% of known filed dollars covered**.

| Line | Defensible interpretation |
|---|---|
| Cost per completed task | Runtime allocation only: a hypothetical 1/2/4-minute run costs $0.00168/$0.00336/$0.00672 including EC2 and IP, or $0.0000095/$0.0000190/$0.0000380 per attempted filing at 177 attempts ($0.0000166/$0.0000333/$0.0000665 per admitted filing at 101 admissions). These are ×0.5/×1/×2 runtime scenarios, **not measured EC2 timings**. If this is the only batch in an always-on month, allocating the full $76.77 costs about **$0.76 per admitted filing**, plus variable charges. |
| Latency | Measured by Shravya on an Apple M3 Pro laptop (18 GB): **9.7 seconds** for the five core stages with seven cleaning rules; acquire 0.38 s, parse 5.23 s, clean 2.34 s, reconcile 1.20 s, report 0.55 s. This is **0.053 s per SUB filing** (9.7/183), or **0.055 s per attempted filing** (9.7/177). Stage timings used `/usr/bin/time -p dvc repro --force -s <stage>`; exclude the initial DVC download and the subsequently added affiliation stage. EC2 runtime has not been benchmarked. |
| Human time replaced (assumption) | Assume **1 analyst hour per filing** to rebuild and reconcile manually. For the 101 admitted filings, ×0.5/×1/×2 gives **50.5/101/202 analyst hours per quarter** of gross manual effort potentially displaced. This is a planning assumption, not measured net savings: review, maintenance and all excluded filings still require human effort. For the 63 unresolved exclusions, a separate assumed 5/10/20 minutes of further investigation each adds 5.25/10.5/21 hours. |
| Quality | 101/177 admitted (57.1%), $240.917B/$542.176B known filed fair value (44.4%); 8 attempts lack a usable total and their unknown dollars are outside that denominator. Frozen sample: 19/20 matches; the exception is an equity quantity represented as principal. Reconciliation passing does not establish every field's correctness. |
| Scale (estimate) | The SEC list checked 2026-10-30 has **22 ZIPs from 2022 Q4 through September 2026**, totaling approximately 478.57 listed MB, versus 40.23 listed MB for our April–June inputs. Assuming runtime scales linearly with compressed bytes on the same laptop: **9.7 × 478.57/40.23 ≈ 115 seconds** for all listed releases. Assuming EC2 takes 3× that time gives **346 seconds (5.8 minutes)** and **$0.0097 compute + IPv4 allocation**, at $0.10076/hour; storage, downloads, requests and human review are additional. This is an extrapolation, not a measured historical rerun or an upper bound; formats, filing mix and memory needs may differ. |

The earlier ~80-second estimate used a smaller ~340 MB inventory. The current
22-file inventory includes July–September 2026 and replaces that estimate. SEC
listed sizes are used consistently for the ratio; ZIP bytes are only a workload
proxy. The optional affiliation stage is excluded from the timing projection.

## Build versus buy

The team extended the starter loaders with release-aware parsing, seven guarded
cleaning rules, reconciliation, source provenance, triage reports, and a demo app.
We reuse SEC datasets and DVC instead of OCRing every filing. Source-filing checks
remain necessary for ambiguous cases. No commercial-product price comparison or
claim that the pipeline replaces a human analyst has been established.

## Reproduce the inventory and measurements

```bash
aws ec2 describe-instances --instance-ids i-089c6d5b3bfd4bd97 --profile lantern --region us-east-1
aws ec2 describe-volumes --volume-ids vol-082f5c1d151ea23a5 --profile lantern --region us-east-1
aws ec2 describe-addresses --profile lantern --region us-east-1
aws s3 ls s3://lantern-team2-dvc-fall-2026/cs2b/ --recursive --summarize --profile lantern
```

For a runtime benchmark, use a separate checkout with restored inputs, then run
`/usr/bin/time -v dvc repro --force` on EC2 (GNU time). Record wall time, maximum
resident set size, instance type, input bytes, and revision. Do not overwrite the
frozen deployment's outputs just to benchmark it. Actual billed spend requires
Cost Explorer or the AWS bill; it was not queried in this review.

## References

- [SEC BDC release inventory and ZIP sizes](https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets), checked 2026-10-30.
- Laptop measurement: Shravya, 2026-10-30; recorded in commit `63e5cd1`.

- [AWS EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [AWS public us-east-1 EC2 price catalog (CSV)](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv)
- [AWS M7i and M7i-flex specifications](https://aws.amazon.com/ec2/instance-types/m7i/)
- [AWS EBS pricing](https://aws.amazon.com/ebs/pricing/)
- [AWS public IPv4 pricing](https://aws.amazon.com/vpc/pricing/)
- [AWS S3 pricing](https://aws.amazon.com/s3/pricing/)
- Project evidence: `coverage.json`, `spot_check.csv`, `dependency_check.md`, and `data/triage.csv`.
