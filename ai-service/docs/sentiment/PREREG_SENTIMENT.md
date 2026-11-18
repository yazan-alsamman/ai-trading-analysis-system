# Gold-news sentiment (FinBERT) and next-day volatility (registration draft)

**Status: DRAFT, 2026-11-18. Not approved. Nothing below has been run; no outcome has been seen.**
Author: Yazan (with Claude). Reviewer: Fadi. Repository home once approved:
`ai-service/docs/sentiment/PREREG_SENTIMENT.md`. No model may be scored on the test years, and no
volatility outcome may be computed, before Fadi approves this text (date and approving commit in
§13). Changes after approval are dated addenda, written before the run they affect.

This delivers the plan's promised feature "news sentiment via fine-tuned FinBERT" for gold. It has
two parts: (1) a headline classifier that reads sentiment **from gold's point of view**, and (2) a
daily sentiment index and a test of whether it adds to the forecast of gold's **next-day
volatility**. Direction is not the product: the research record says gold's direction is not
forecastable for trading, and nothing here changes that claim. No trade is simulated.

It is separate from `docs/news/PREREG_NEWS.md` (scheduled US releases). The sentiment index is not
a feature of that registration; adding it there later needs a new registration.

## 1. Questions and hypotheses

| Id | Part | Question | Role |
| --- | --- | --- | --- |
| **S1** | Classifier | A fine-tuned transformer beats TF-IDF + logistic regression on gold-perspective sentiment (macro-F1, test years) | **primary** |
| **S2** | Index | Adding the sentiment index to HAR + news count improves the out-of-sample forecast of next-day log volatility | **primary** |
| S3 | Classifier | Stage-1 training on FinancialPhraseBank helps (FPB → gold vs gold only) | secondary, ablation |
| S4 | Index | Negative sentiment matters more than positive (asymmetry) | secondary |
| S5 | Index | An index built only from forward-looking headlines (Future Information = 1) does better than the full index | secondary |
| S6 | Classifier | Accuracy holds on live 2026 headlines (hand-labelled set, §2.4) | secondary, domain shift |

H0 for every row: no improvement. S1 and S2 decide what is served (§11); secondary results are
reported whatever they show.

## 2. Data

### 2.1 Headlines (labelled)

- **Gold news dataset** (Sinha and Khandait, "Impact of News on the Commodity Market: Dataset and
  Results", arXiv:2009.04202; Kaggle). About 10,570 English headlines, about 2000 to 2019, with a
  publication **date** (no time), and labels: Price Sentiment (positive / negative / neutral /
  none), Price Direction Up / Constant / Down, Past Information, Future Information, Asset
  Comparison. Licence **CC BY-NC-ND 4.0**.
- **FinancialPhraseBank** (Malo et al. 2014), subset `Sentences_AllAgree`, used only for stage-1
  training (S3). Licence **CC BY-NC-SA 3.0**.
- **Licence rules (decided 2026-11-18):** the project is non-commercial. Neither dataset is
  committed to this public repository; the repository holds only a download script with the
  files' SHA-256. Trained weights are not published; they live on the server only (§11). Both
  datasets are cited in the report.

### 2.2 Labels (decided 2026-11-18)

- Target = the gold dataset's **Price Sentiment**, which is from gold's point of view. "none"
  (headline not about gold's price) is mapped to **neutral** for training and given weight 0 in the
  index (§5).
- FinancialPhraseBank's labels are from a company / equity investor's point of view; they are
  never used as the target, only as stage-1 training (S3).

### 2.3 Prices

- **Primary (decided 2026-11-18):** Dukascopy XAUUSD **daily** candles, bid, volumes, flats
  excluded, downloaded 2026-11-18 with `npx dukascopy-node -i xauusd -from 2000-01-01
  -to 2026-11-18 -t d1 -f csv -p bid -v`: 8,183 bars, 2000-01-03 to 2026-11-16, day boundary
  **00:00 UTC**. Not committed (terms unclear); the repository keeps the command and the file's
  SHA-256.
- **Known issues (checked 2026-11-18, prices only, no headline or model touched):** 2000-2002 have
  rounded prices, a different volume unit and 94 bars with impossible OHLC (high below open/close
  or low above): those years are not used for any volatility figure. From 2003 there is a short
  **Sunday bar** (the Sunday evening open; median range 0.3% vs 1.2-1.4% on weekdays): it is
  **merged into Monday** (open = Sunday open, high/low = max/min of both, close = Monday close).
- **Cross-check only:** FxPro MT5 XAUUSD D1 export (requested from Fadi on 2026-11-18), else a
  free daily series (Stooq). Used for gate G2; never fills missing years. Years Dukascopy does not
  cover are dropped from the study.
- None of these years touch the lockbox (from 2026-01-10).

### 2.4 Live headlines (S6 and serving)

- Finnhub (forex and general news) and the backend's existing `investinglive_rss`, filtered by the
  frozen keyword list in Appendix A, pushed through `POST /ingest/news`.
- **Live test set:** about 300 live gold headlines collected from the start of the live feed,
  labelled independently by two people (Yazan and one teammate) with the guide in Appendix B
  **before** any model scores them. Agreement reported as Cohen's kappa; disagreements resolved by
  discussion, and the resolved label is the truth.

### 2.5 Splits (by date, never random)

| Split | Dates | Use |
| --- | --- | --- |
| Train | first date to 2012-12-31 | fitting |
| Validation | 2013-01-01 to 2015-12-31 | model and hyperparameter choice, early stopping |
| **Test** | 2016-01-01 to end of data | read **once** for S1; the only years used for S2 |

If the test split has fewer than 1,500 headlines after deduplication, the boundaries move to
train ≤ 2011 / validation 2012-2014 / test 2015+ (decided on the count, before any model).

## 3. Data gates (before any model; each must pass or be reported)

| Gate | Check | Pass rule |
| --- | --- | --- |
| G1 duplicates | Normalise headlines (lower case, strip punctuation and numbers); drop exact duplicates; near-duplicates (token Jaccard ≥ 0.8 within ±3 days) keep the first | counts per year reported; no headline text appears in two splits |
| G2 prices | Dukascopy D1 vs the cross-check series: daily close correlation and share of days with \|log return difference\| > 0.5% | correlation ≥ 0.99; flagged days listed and investigated |
| G3 day alignment | Broker day close (Europe/Athens) vs headline date: count headlines whose date falls on a weekend or holiday | reported; such headlines move to the next trading day |
| G4 label balance | Class shares per split | reported; class weights set from train only |
| G5 coverage | Trading days with zero headlines, per year | reported |

## 4. Classifier (part 1)

### 4.1 Baselines

| Id | Model |
| --- | --- |
| C0 | Majority class of train |
| C1 | Loughran-McDonald lexicon: (positive − negative word count), thresholds tuned on validation |
| **C2** | TF-IDF (word 1-2 grams + char 3-5 grams) + logistic regression, C tuned on validation |
| C3 | ProsusAI/finbert, no fine-tuning, labels used as given |
| C4 | Gemini zero-shot with the frozen prompt in Appendix C (temperature 0) |

### 4.2 Candidates

| Id | Model |
| --- | --- |
| F1 | ProsusAI/finbert fine-tuned on gold train |
| F2 | ProsusAI/finbert: stage 1 on FinancialPhraseBank, stage 2 on gold train |
| D1 | microsoft/deberta-v3-base fine-tuned on gold train |

Fine-tuning: max length 64, AdamW, learning rate in {2e-5, 3e-5, 5e-5}, batch 32, up to 5 epochs
with early stopping on validation macro-F1, class-weighted cross-entropy, warm-up 10%. Grid chosen
on validation only. Each final configuration trained with **5 seeds** (20261118 to 20261122).

### 4.3 Evaluation

- **Metric:** macro-F1 over positive / negative / neutral; also per-class F1, confusion matrix,
  accuracy.
- The candidate with the best mean validation macro-F1 is the **chosen model**, decided before the
  test split is opened.
- **S1 passes** if the chosen model's test macro-F1 (mean of 5 seeds) is above C2's, and the
  headline-level bootstrap (10,000 resamples, seed 20261119) 95% interval of the difference is
  above zero.
- **S3:** F2 vs F1 on test, same bootstrap; reported.
- **S6:** chosen model and C2 scored on the live test set; macro-F1 with bootstrap interval.

## 5. Daily index (part 2)

For trading day t (broker day, §3 G3), over the test-split headlines of day t scored by the
**chosen model** (frozen, never trained on these years):

- `sent_mean` = mean of P(positive) − P(negative) over headlines (excluding "none"-type headlines
  predicted neutral with P(neutral) > 0.9, which carry no gold-price content);
- `neg_share` = share of headlines predicted negative;
- `news_count` = log(1 + number of headlines);
- `sent_disp` = standard deviation of P(positive) − P(negative) (0 if fewer than 2 headlines);
- `no_news` = 1 if there are no headlines (then the other three are 0).

S5 repeats the index with Future Information = 1 headlines only.

## 6. Volatility study

- **Target:** y_{t+1} = log of the Garman-Klass daily variance of day t+1 from the Dukascopy D1 bar.
- **Baseline (B):** HAR on log GK variance (day t, mean of t−4..t, mean of t−21..t), |r_t|,
  1{r_t < 0}·|r_t|, weekday dummies, **plus `news_count` and `no_news`**.
- **Model (S):** B + `sent_mean` + `neg_share` + `sent_disp`.
- **S4 model:** B + positive and negative parts of `sent_mean` separately.
- Fitted by OLS (Newey-West errors, 5 lags, for the in-sample table only).
- **Out of sample:** expanding window inside the test years: first forecast after 250 trading
  days, refit every 20 days, one-step-ahead forecasts to the end.
- **Robustness:** the same with a two-day lead (index of t predicting y_{t+2}), because headlines
  carry a date but no time.

### 6.1 S2 pass rule (all must hold)

1. Mean QLIKE of S below B, Diebold-Mariano one-sided p < 0.05 (Newey-West variance, 5 lags);
2. **Permutation:** the three sentiment columns shuffled together across days (1,000 times,
   refit each, seed 20261120); the real QLIKE gain beats at least 95% of the shuffled gains;
3. the sign of the gain is the same in the two-day-lead robustness run (reported; not required to
   be significant).

The test years give about 1,000 trading days; low power is stated in the report. A null result
is a valid result.

## 7. Reported with it (decide nothing)

1. Gate results G1-G5 in full.
2. Error analysis: 50 test headlines misclassified by the chosen model, with the labels.
3. In-sample OLS table of S with Newey-West errors.
4. Plot of `sent_mean` (20-day mean) against GK volatility over the test years.
5. Calibration (reliability) of the chosen model's probabilities on test.
6. Inference time per headline on the server CPU (ONNX vs PyTorch).

## 8. Data use

- Train + validation: everything in §3-§4 up to choosing the model. No look at test.
- Test (2016+): one run for S1/S3, then one run for S2/S4/S5 with the frozen chosen model. A rerun
  only after a dated addendum (bug fix), logged as a new look.
- Live test set: labelled before scoring; read once for S6.

## 9. Bookkeeping

Training notebooks (Colab/Kaggle): `ai-service/notebooks/sentiment/`; code
`app/research/news_sentiment.py`, `python -m app research sentiment gates|classify|index|vol`,
committed before each run. Reports: `docs/sentiment/gates.md`, `docs/sentiment/classifier_result.md`,
`docs/sentiment/vol_result.md`. Every run logged in `docs/phase3/TRIALS.md` as a forecast look; it
simulates no trade and adds nothing to N for any strategy's Deflated Sharpe.

## 10. Leakage rules (decided 2026-11-18)

1. The index of day t is used only for day t+1 (and t+2 in robustness), never for day t.
2. The baseline already holds day t's volatility and return: the question is what sentiment adds
   beyond prices and beyond news count.
3. The index is built only from headlines the model never trained on (test years).
4. Deduplication (G1) happens before the split.

## 11. Serving (after the result; not part of the test)

- Served if S1 passes; otherwise the better of C2 and the chosen model is served and the report
  says so. The daily index is shown as a dashboard figure in any case; it is used as a volatility
  input only if S2 passes.
- Separate container `news-nlp` (no torch): ONNX export of the chosen model, **fp32**,
  onnxruntime on CPU. Parity check before deployment: ONNX vs PyTorch probabilities on the test
  headlines, max absolute difference < 1e-4.
- Backend Celery task every 5 minutes: unscored gold-tagged articles → `news-nlp` → existing
  columns `sentiment_label`, `sentiment_score` (= P(positive) − P(negative)),
  `sentiment_model = "finbert-gold-v1"`. Daily task computes and stores the §5 index.
- Weights in `/opt/trading/models/finbert-gold-v1/` on the server, mounted as a volume; never in
  the repository. Feature flag in `.env`, off by default.
- A frozen model version changes only by a new registration.

## 12. Open before approval

1. Dukascopy daily XAUUSD file obtained (first date, day boundary); Fadi's MT5 D1 export as cross-check (asked 2026-11-18).
2. Confirm the Kaggle file's exact row count and date range; set the split boundaries by §2.5.
3. Pin Hugging Face model revisions (ProsusAI/finbert, microsoft/deberta-v3-base) in an addendum
   before training.
4. Finnhub free-tier terms and rate limit checked before the live feed.
5. Name the second annotator for the live test set.

## 13. Approval

Approved by: — Date: — Commit: —

## Appendix A: live keyword filter (case-insensitive, whole word)

gold, bullion, XAU, XAUUSD, precious metal(s), Comex gold, SPDR Gold, GLD, central bank gold,
safe haven, Fed, FOMC, Powell, Treasury yields, real yields, dollar index, DXY.
An article is "gold-tagged" if its title or summary has at least one of gold / bullion / XAU /
XAUUSD / precious metal(s) / Comex gold / SPDR Gold / GLD, or at least two of the remaining terms.

## Appendix B: labelling guide (live test set)

Label each headline by its likely effect on **gold's price**, as written, without looking up what
happened next:
- **positive:** good for gold (gold up, dollar or yields down, risk-off, dovish Fed, inflation fear);
- **negative:** bad for gold (gold down, dollar or yields up, risk-on, hawkish Fed);
- **neutral:** about gold but no clear effect, or not about gold's price.

## Appendix C: Gemini zero-shot prompt (C4)

"You classify financial news headlines by their likely effect on the price of gold. Answer with
exactly one word: positive, negative, or neutral. Headline: {headline}"
