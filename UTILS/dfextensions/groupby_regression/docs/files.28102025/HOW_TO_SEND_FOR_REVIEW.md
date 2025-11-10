# How to Send Files for Review - Quick Guide

**For:** Marian Ivanov  
**Purpose:** Step-by-step instructions to send to Claude and Gemini

---

## 📦 Files You Have

**From GPT:**
1. test_groupby_regression_sliding_window.py (tests)
2. groupby_regression_sliding_window.py (implementation)

**Review Forms:**
3. CLAUDE_REVIEW_FORM.md
4. GEMINI_REVIEW_FORM.md

**Optional Context:**
5. PHASE7_IMPLEMENTATION_PLAN.md

---

## 🎯 Option A: Send Both Files Together (Recommended)

### To Claude

**Upload files:**
1. test_groupby_regression_sliding_window.py
2. groupby_regression_sliding_window.py
3. CLAUDE_REVIEW_FORM.md
4. PHASE7_IMPLEMENTATION_PLAN.md (optional)

**Message:**
```
Please review Phase 7 M7.1 implementation.

Files to review:
- test_groupby_regression_sliding_window.py (26 tests from GPT)
- groupby_regression_sliding_window.py (implementation from GPT)

Instructions:
- Complete CLAUDE_REVIEW_FORM.md
- Run pytest and report results
- Focus on architecture, code quality, API compliance

Reference:
- PHASE7_IMPLEMENTATION_PLAN.md (specification)

Thank you!
```

---

### To Gemini

**Upload files:**
1. test_groupby_regression_sliding_window.py
2. groupby_regression_sliding_window.py
3. GEMINI_REVIEW_FORM.md
4. PHASE7_IMPLEMENTATION_PLAN.md (optional)

**Message:**
```
Please review Phase 7 M7.1 implementation.

Files to review:
- test_groupby_regression_sliding_window.py (26 tests from GPT)
- groupby_regression_sliding_window.py (implementation from GPT)

Instructions:
- Complete GEMINI_REVIEW_FORM.md
- Focus on algorithm correctness, physical model, numerical stability
- Validate mathematical soundness

Reference:
- PHASE7_IMPLEMENTATION_PLAN.md (specification)

Thank you!
```

---

## 🎯 Option B: Review in Two Stages

### Stage 1: Review Tests Only (Before Implementation)

**To Claude:**
```
Please review test suite quality.

File: test_groupby_regression_sliding_window.py
Form: CLAUDE_REVIEW_FORM.md (Part 1 only)

Check:
- All 26 tests present
- Good assertions
- Clear docstrings
- Proper structure

Implementation will come later.
```

**To Gemini:**
```
Please review test suite correctness.

File: test_groupby_regression_sliding_window.py
Form: GEMINI_REVIEW_FORM.md (Part 1 & 2 only)

Check:
- Physical model realistic
- Algorithms correct
- Statistical validity

Implementation will come later.
```

---

### Stage 2: Review Implementation (After Tests Approved)

**To Claude:**
```
Tests approved! Now review implementation.

Files:
- test_groupby_regression_sliding_window.py (approved)
- groupby_regression_sliding_window.py (NEW)

Form: CLAUDE_REVIEW_FORM.md (complete all parts)

First: Run pytest and report results
Then: Complete full review
```

**To Gemini:**
```
Tests approved! Now review implementation.

Files:
- test_groupby_regression_sliding_window.py (approved)
- groupby_regression_sliding_window.py (NEW)

Form: GEMINI_REVIEW_FORM.md (complete all parts)

Focus: Algorithm implementation, numerical correctness
```

---

## 📧 Email Template (If Using Email)

### Subject: Phase 7 M7.1 Review Request

```
Hi [Claude/Gemini],

I need your review of Phase 7 M7.1 (Sliding Window GroupBy Regression).

Files attached:
- test_groupby_regression_sliding_window.py (tests)
- groupby_regression_sliding_window.py (implementation)
- [CLAUDE/GEMINI]_REVIEW_FORM.md (review checklist)

Please:
1. Run pytest on the test suite
2. Complete the review form
3. Return findings within 2-3 days

Context:
- 26 tests created by GPT
- Zero-copy accumulator implementation
- Statsmodels integration (OLS, WLS)
- Target: 3D-6D sparse binned data

Questions? Let me know!

Thanks,
MI
```

---

## ⏱️ Timeline Expectations

**Claude review:** 2-3 days
- Focus: Architecture, code quality, tests passing

**Gemini review:** 2-3 days  
- Focus: Algorithm correctness, physical model

**Your decision:** 1 day after both reviews received

**Total:** ~1 week from submission to approval

---

## ✅ Checklist Before Sending

**Files ready:**
- [ ] test_groupby_regression_sliding_window.py (from GPT)
- [ ] groupby_regression_sliding_window.py (from GPT)
- [ ] CLAUDE_REVIEW_FORM.md (downloaded from outputs)
- [ ] GEMINI_REVIEW_FORM.md (downloaded from outputs)
- [ ] PHASE7_IMPLEMENTATION_PLAN.md (optional context)

**Message prepared:**
- [ ] Clear instructions
- [ ] Files listed
- [ ] Timeline mentioned
- [ ] Contact info for questions

**You're ready to:**
- [ ] Send to Claude
- [ ] Send to Gemini
- [ ] Wait for reviews
- [ ] Make decision using MI_COORDINATION_FORM.md

---

## 🎯 What Happens Next

**Day 0 (Today):**
- You send files to Claude and Gemini

**Days 1-2:**
- Claude and Gemini review independently
- They may ask clarifying questions

**Day 3:**
- You receive CLAUDE_REVIEW_FORM.md (completed)
- You receive GEMINI_REVIEW_FORM.md (completed)

**Day 4:**
- You review both forms
- Fill out MI_COORDINATION_FORM.md
- Make decision (approve/fix/reject)
- Communicate decision

**Day 5+ (if approved):**
- Commit to git
- Update documentation
- Plan M7.2

---

## 💡 Tips

**Be patient:** Good reviews take time

**Trust the process:** Two expert reviews catch issues

**Ask questions:** If forms unclear, ask reviewers to explain

**Celebrate progress:** Getting to review stage is huge!

---

## 📞 Quick Reference

**Files location:** `/mnt/user-data/outputs/`

**View files:**
- [CLAUDE_REVIEW_FORM.md](computer:///mnt/user-data/outputs/CLAUDE_REVIEW_FORM.md)
- [GEMINI_REVIEW_FORM.md](computer:///mnt/user-data/outputs/GEMINI_REVIEW_FORM.md)
- [MI_COORDINATION_FORM.md](computer:///mnt/user-data/outputs/MI_COORDINATION_FORM.md)

**Upload location:** Your preferred platform (email, chat, etc.)

---

## 🚀 Ready?

**Next action:** Send files to Claude and Gemini using templates above

**Expected result:** Two completed review forms within 2-3 days

**Your role:** Coordinate and make final decision

**Status:** ✅ Ready to send
