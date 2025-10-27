# Sliding Window GroupBy Regression - Q&A Document

**Status:** Living document  
**Last updated:** 2025-10-27  
**Purpose:** Track complex concepts, design decisions, and review feedback

---

## 2. Example Data - itteration 1 (27.10,2025 11:00)
Your version is too long and includes parts that do not reflect the reality of the project. The main purpose of the document is to motivate the development of a generic interface.

I am not sure how to proceed. I suggest asking GPT and Gemini to review the conceptual part of section 2. Please provide a question based on my considerations below. Before proceeding, we need to resolve the issues with the scope, purpose, and length of this section.

Additionally, in this particular case, it may be simpler if I edit it directly. Should I do that?

Section Dataset A: TPC Spatial Distortion Maps (Test Data) was based on my example, so it closely matches our actual situation.

2.3 Dataset B: TPC Temporal Evolution (Production Scale) was not described by me, so it does not reflect reality. I can prepare a shortened version. In this section, I want to highlight one important aspect from real practice: I use modified variables of interest – for example, instead of pt, I use q/pt, as many QA variables are more linear in q/pt.



## Motivation - Iteration 1 (2025-10-27 07:00)

Before answering the questions, I would like to describe in more detail what is being done and why.

* 0.) We are trying not only to describe a multidimensional function but also to estimate statistical 
   properties of the probability density function (PDF) itself (e.g. using quantiles).
* 1.) LHC/my specific: We are working with both unbinned and binned data, as well as machine learning 
   algorithms, depending on data availability. In the case of ALICE, we usually have a huge amount of data. 
   For example, for tracks we have 500 kHz × 10 → 5 × 10^6 tracks per second, measuring for O(10–15 hours) per 
   day. This data is either histogrammed in multidimensional histograms or, by default, we sample it using 
   "balanced semi-stratified" sampling, populating the variables of interest homogeneously (e.g. flat pt, flat PID).
   This is very important as PDF of Pt and PID is highly unbalanced (exponential, power-law, etc).
   With this approach, we reduce the input data volume by an order of magnitude and enable iterative refinement  
   of the PDF estimation.
* 2.) Extracting PDF properties in multidimensional space has the advantage of enabling post-fitting of 
   analytical models for normalised data. Quite often, we do not have analytical models for the full distortion 
   in (3D+time), but we can have an analytical model for the delta distortion time evolution. 
   In my current studies, for example, we are fitting a two- exponential phi-symmetric model of distortion 
   due to common electric field modification.

### Initial Questions (Iteration 1)

**Q1:** Does this capture your motivation accurately?
**A:** Several factors must be considered. Often we have large data but are limited by memory/CPU. Using >4GB in memory is problematic. Pre-sampling helps as original data is statistically highly unbalanced. The problem is not only sparsity - data is "random" and we need substantial statistics per bin.

**Q2:** Should I emphasize more?
**A:** Rewrite to emphasize statistical/mathematical considerations - PDF estimation and functional decomposition using partial models and factorization. Show ALICE examples. Software must be reusable.

**Q3:** Tone - mathematical vs practical?
**A:** Will ask GPT/Gemini. Some mathematics would be good but need balance.

**Q4:** Missing key points?
**A:** Emphasize statistical estimation problem. Motivation should be grounded in defined problems with ALICE examples. Highlight reusability and API design. Note: presented at forums but difficult to explain - people didn't understand statistical estimation, factorization, and usage in analytical model fitting with data renormalization.

**Q5:** Add diagram?
**A:** Yes, sparse 3D bins with ±1 neighborhood would help.

---

## Motivation - Iteration 2 (2025-10-27 09:00)

### Additional Use Cases Added

* Distortion maps (already in use)
* Performance parameterization (e.g. track pT resolution as function of pT, eta, occupancy, time)
  * Track matching resolution and biases
  * V0 resolution and biases
  * PID resolution and biases
  * Efficiency maps
  * QA variables (chi2, number of clusters, etc.)
  * Usage in MC-to-Data remapping
* Note: RootInteractive is only a small subproject for interactive visualisation of extracted data

### Review Questions (Iteration 2)

**Q1: Does Section 1 now accurately capture the key concepts?**

*PDF estimation focus?*
- More or less OK ✓

*Balanced sampling strategy?*
- Mentioned but need more details
- In some use cases we sample down by factor of 10³–10⁴ to obtain manageable data size
- **Action:** Added range 10×-10⁴× with typical 10²-10³× in Section 1.3.1 ✓

*Factorization approach?*
- Explained with TPC example
- **Action:** Added note about temporal resolution (5-10 min maps vs O(s) for fluctuations) ✓

*Connection to RootInteractive?*
- RootInteractive is just one subproject for interactive visualization
- **Action:** Added clarification that sliding window is server-side preprocessing ✓

**Q2: Tone and depth**

*Is mathematical level appropriate?*
- Will ask GPT/Gemini for feedback → **See REVIEW_REQUEST_SECTION1.md**

*Should I add equations?*
- Yes, would enhance clarity
- But ask GPT/Gemini first → **See REVIEW_REQUEST_SECTION1.md**

*Is ALICE example clear?*
- Need distortion map AND performance parameterization examples
- **Action:** Added performance parameterization example in Section 1.1 ✓
- **Action:** Expanded use cases in Section 1.5 ✓

**Q3: Missing elements**

*Key concepts still missed?*
- Performance parameterization case added at beginning
- Can mention in motivation categories and later in example sections
- **Action:** Added to Section 1.1 and 1.5 ✓

**Q4: Structure**

*Are subsections (1.1-1.5) logical?*
- Structure OK for now
- Will ask GPT/Gemini → **See REVIEW_REQUEST_SECTION1.md**

**Q5: Next steps**

*Send to GPT/Gemini or continue to Section 2?*
- **Decision:** Need GPT/Gemini review BEFORE proceeding to Section 2
- **Action:** Created REVIEW_REQUEST_SECTION1.md with detailed questions ✓

---

## Status Summary

**Section 1 - Motivation:**
- Iteration 2 draft complete
- Incorporates all user feedback from 2025-10-27 09:00
- Ready for external review

**Next Steps:**
1. Send to GPT-4 for review
2. Send to Gemini for review  
3. Address critical issues from both reviewers
4. Finalize Section 1
5. Proceed to Section 2 (Example Data)

**Files:**
- `SLIDING_WINDOW_SPEC_DRAFT.md` - Main specification document
- `REVIEW_REQUEST_SECTION1.md` - Review questions for GPT/Gemini
- `Q_A.md` - This file (Q&A tracking)

---

## Active Questions for Next Iterations

[None currently - awaiting GPT/Gemini feedback]

---

## Design Decisions Log

[To be populated during Section 6 discussion]

---

## Archived Questions

[To be populated as questions are resolved]
