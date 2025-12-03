# NewsRAG Cost Analysis - Bedrock Batch Inference Architecture

## Monthly Cost Breakdown (12-hour scraping schedule = 60 runs/month)

### AWS Bedrock Costs

#### 1. Batch Inference (Claude 3 Haiku Classification)
- **Model**: Claude 3 Haiku
- **Pricing**: 
  - Input: $0.00025 per 1K tokens (50% batch discount = **$0.000125/1K tokens**)
  - Output: $0.00125 per 1K tokens (50% discount = **$0.000625/1K tokens**)
- **Usage per run**:
  - ~300 articles scraped per run
  - ~200 tokens per article (title + 1000 chars content preview)
  - Input tokens: 300 × 200 = 60,000 tokens = 60K tokens
  - Output tokens: 300 × 5 = 1,500 tokens = 1.5K tokens (single word category)
- **Cost per run**:
  - Input: 60K × $0.000125 = **$0.0075**
  - Output: 1.5K × $0.000625 = **$0.00094**
  - Total per run: **$0.00844**
- **Monthly cost (60 runs)**: 60 × $0.00844 = **$0.506**

#### 2. Embeddings (Titan Embed Text v2)
- **Model**: Amazon Titan Embed Text v2
- **Pricing**: $0.00002 per 1K input tokens
- **Usage per run**:
  - ~200 articles after classification filtering (33% rejected)
  - ~100 tokens per article (title + summary/content preview)
  - Total tokens: 200 × 100 = 20,000 tokens = 20K tokens
- **Cost per run**: 20K × $0.00002 = **$0.0004**
- **Monthly cost (60 runs)**: 60 × $0.0004 = **$0.024**

**Total Bedrock Monthly Cost**: $0.506 + $0.024 = **$0.53/month**

---

### AWS Lambda Costs

#### Lambda Execution
- **Pricing**: 
  - $0.20 per 1M requests
  - $0.0000166667 per GB-second
- **Configuration**: 1024 MB (1 GB) memory
- **Usage**:
  - 60 scrape invocations/month (Phase 1)
  - 60 process invocations/month (Phase 2)
  - Total: 120 invocations/month

#### Phase 1 - Scrape & Submit Batch Job
- **Duration**: ~60 seconds (scraping + preparing batch input)
- **GB-seconds**: 1 GB × 60s = 60 GB-seconds
- **Cost per run**: 60 × $0.0000166667 = $0.001
- **Monthly cost**: 60 × $0.001 = **$0.06**

#### Phase 2 - Process Results & Embeddings
- **Duration**: ~400 seconds (200 articles × 1s embedding + 200s processing)
- **GB-seconds**: 1 GB × 400s = 400 GB-seconds
- **Cost per run**: 400 × $0.0000166667 = $0.00667
- **Monthly cost**: 60 × $0.00667 = **$0.40**

#### Request Cost
- 120 invocations/month
- Cost: 120 / 1,000,000 × $0.20 = **$0.000024** (negligible)

**Total Lambda Monthly Cost**: $0.06 + $0.40 = **$0.46/month**

---

### AWS S3 Costs

#### Storage
- **Pricing**: $0.023 per GB/month (Standard)
- **Usage**:
  - Batch input files: ~300 articles × 2KB = 600KB per run
  - Batch output files: ~300 results × 500 bytes = 150KB per run
  - Articles JSON: ~300 articles × 3KB = 900KB per run
  - Total per run: ~1.65 MB
  - With 7-day lifecycle (14 runs stored): 14 × 1.65 MB = **23 MB = 0.023 GB**
- **Monthly storage cost**: 0.023 GB × $0.023 = **$0.00053**

#### Requests
- **PUT requests**: $0.005 per 1,000 requests
- **GET requests**: $0.0004 per 1,000 requests
- **Usage per run**:
  - 3 PUT (input, articles, output)
  - 3 GET (read files)
- **Monthly cost**: (180 PUT + 180 GET) / 1000 × $0.005 = **$0.0009**

**Total S3 Monthly Cost**: $0.00053 + $0.0009 = **$0.00143** (negligible)

---

### MongoDB Atlas Costs

#### M0 Free Tier (Current Setup)
- **Storage**: 512 MB (sufficient for ~50K articles with embeddings)
- **Network**: 10GB/month outbound
- **Cost**: **FREE**

#### Future (if scaling beyond 512 MB)
- **M2 Shared Cluster**: $9/month
  - 2 GB storage
  - 20 GB outbound
  - Supports ~200K articles

**Current MongoDB Cost**: **$0.00/month**

---

### Bedrock Batch Job Processing Time

#### Batch Job Duration
- **Articles**: ~300 per run
- **Processing time**: Batch jobs typically complete in 30-60 minutes
- **No rate limiting issues**: AWS handles throttling internally
- **Cost savings**: 50% discount compared to on-demand inference

---

## Total Monthly Cost Summary

| Service | Cost/Month |
|---------|------------|
| **Bedrock Batch Inference (Claude)** | $0.51 |
| **Bedrock Embeddings (Titan)** | $0.02 |
| **Lambda Execution** | $0.46 |
| **S3 Storage & Requests** | $0.00 |
| **MongoDB Atlas (M0)** | $0.00 |
| **TOTAL** | **~$1.00/month** |

---

## Cost Comparison: Batch vs On-Demand

### Previous On-Demand Approach (Failed due to throttling)
- Claude on-demand: $0.00025/1K input × 60K = $0.015/run
- Monthly (60 runs): $0.015 × 60 = **$0.90/month**
- **Problem**: Hit rate limits, caused timeouts

### New Batch Approach
- Claude batch: $0.000125/1K input × 60K = $0.0075/run
- Monthly (60 runs): $0.0075 × 60 = **$0.45/month**
- **Savings**: 50% cheaper + no throttling issues

---

## Annual Cost Projection

### Year 1 (M0 Free Tier)
- **Bedrock**: $0.53 × 12 = $6.36
- **Lambda**: $0.46 × 12 = $5.52
- **S3**: $0.00 × 12 = $0.00
- **MongoDB**: $0.00 × 12 = $0.00
- **Total Year 1**: **~$12/year**

### After Scaling (M2 Cluster - 200K articles)
- **Bedrock**: $6.36
- **Lambda**: $5.52
- **S3**: $0.00
- **MongoDB M2**: $9 × 12 = $108
- **Total with M2**: **~$120/year**

---

## Cost Optimization Tips

1. **Reduce scraping frequency**: 
   - 12h → 24h schedule = 50% cost reduction
   - Annual cost: $6/year

2. **Filter before classification**:
   - Use keyword pre-filter to reduce batch size by 30-40%
   - Save ~$0.15/month on Claude costs

3. **Batch embedding generation**:
   - Already implemented with 1s delays
   - Optimal for Titan rate limits

4. **S3 lifecycle policies**:
   - Already set to 7 days
   - Keeps storage costs near zero

5. **MongoDB optimization**:
   - M0 sufficient for ~12 months (30K-50K articles)
   - Delay M2 upgrade as long as possible

---

## Break-Even Analysis

### Cost per Article (End-to-End)
- Total cost: $1.00/month ÷ 60 runs = $0.0167/run
- Articles per run: ~200 (after filtering)
- **Cost per processed article**: $0.0167 ÷ 200 = **$0.000083** (~0.008 cents)

### Components per Article
- Classification: $0.00844 ÷ 300 = **$0.000028**
- Embedding: $0.0004 ÷ 200 = **$0.000002**
- Lambda: $0.00767 ÷ 200 = **$0.000038**
- Storage: negligible

---

## Conclusion

The Bedrock Batch Inference architecture provides:
- ✅ **50% cost savings** on classification vs on-demand
- ✅ **No throttling issues** - AWS handles rate limiting
- ✅ **Scalable** to 1000+ articles per run without code changes
- ✅ **Total cost ~$1/month** for 12K articles/month (200/run × 60 runs)
- ✅ **First year total: ~$12** (using MongoDB M0 free tier)

**ROI**: Extremely cost-effective for news aggregation at this scale. Can process 144K articles/year for under $12.
