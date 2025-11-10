# Sliding Window GroupBy Regression - Specification Document

**Authors:** Marian Ivanov (GSI/ALICE), Claude (Anthropic)  
**Reviewers:** GPT-4, Gemini  
**Date:** 2025-10-27  
**Version:** 0.1 (Draft)

---

## 1. Motivation

### 1.1 The Core Challenge: Probability Density Function Estimation in High-Dimensional Spaces

In high-energy physics and detector calibration, we face a fundamental challenge: **estimating probability density functions (PDFs) and their statistical properties** (quantiles, moments, correlations) from data distributed across high-dimensional parameter spaces. This is not merely a function fitting problem—we must characterize the full statistical behavior of observables as they vary across multiple dimensions simultaneously.

**Note:** While examples in this specification are drawn from ALICE TPC calibration, the underlying statistical challenge—estimating local PDFs in high-dimensional sparse data—is generic to many scientific domains including medical imaging, climate modeling, and financial risk analysis.

**The statistical estimation problem:** Given measurements distributed in an *d*-dimensional binned space, we need to extract reliable statistical estimators (mean, median, RMS (Root Mean Square), MAD (Median Absolute Deviation), quantiles, higher moments) for each bin. However, as dimensionality increases, the **curse of dimensionality** manifests in two critical ways:

1. **Exponential sparsity:** With *n* bins per dimension, we face *n^d* total bins. Even with billions of events (e.g., ALICE collects 5×10^6 tracks/second × 10-15 hours = 180-270 billion tracks/day), many bins remain empty or contain insufficient statistics for reliable PDF characterization.

2. **Unbalanced distributions:** Physical observables often follow highly skewed distributions (exponential mass spectra, power-law transverse momentum), making naive sampling wasteful and leaving critical regions of parameter space under-represented.

**Example from ALICE TPC calibration:**
```
Spatial distortion map binning:
- 3D spatial bins: 152 (x) × 20 (y/x) × 28 (z/x) × 18 (sectors) = ~1.5M bins
- Time evolution: × 90 time slices = 135M total bins
- Target observables: dX, dY, dZ corrections (vector field)
- Even with 270 billion tracks/day, average statistics per bin: ~2000 events
- After quality cuts and balanced sampling: O(10-100) events per bin
```

**Example from performance parameterization:**
```
Track pT resolution as function of (pT, η, φ, occupancy, time):
- 5D parameter space: 50 × 40 × 36 × 20 × 100 = 144M bins
- Target: σ(pT)/pT, resolution biases, efficiency
- Similar challenges: track matching, V0 reconstruction, PID (Particle IDentification) resolution
- Used for MC-to-data remapping and QA (Quality Assurance) variable calibration
```

For bins with <10 events, standard statistical estimators (mean, RMS) have large uncertainties, making robust PDF characterization impossible without additional assumptions.

**Figure 1: Sparse 3D Spatial Bins with ±1 Neighborhood Aggregation**
```
[Placeholder for figure showing:
 - 3D grid of spatial bins (xBin × y2xBin × z2xBin)
 - Center bin highlighted with sparse data (<10 events)
 - ±1 neighbors in each dimension (3×3×3 = 27 bins total)
 - Aggregated data providing sufficient statistics
 - Visual representation of local smoothness assumption]
```
*Figure to be added: Illustration of how sliding window aggregates sparse neighboring bins to enable reliable PDF estimation.*

### 1.2 The Local Smoothness Assumption and Functional Approximation

To overcome statistical sparsity, we must incorporate **prior knowledge** about the physical behavior of our observables. The fundamental assumption is **local smoothness**: physical quantities vary continuously in parameter space, exhibiting correlations between neighboring regions.

This assumption enables **functional approximation** through sliding window aggregation:

**Approach 1: Local constant approximation**  
Aggregate statistics from neighboring bins assuming the PDF properties are approximately constant within a local neighborhood:
$$\mu(\mathbf{x}_0) \approx \text{mean}\{y_i \mid \mathbf{x}_i \in \text{neighborhood}(\mathbf{x}_0)\}$$

**Approach 2: Weighted smoothing**  
Assign distance-based weights to neighbors, giving higher influence to bins closer to the center:
$$\mu(\mathbf{x}_0) \approx \frac{\sum_i w_i(\|\mathbf{x}_i - \mathbf{x}_0\|) \cdot y_i}{\sum_i w_i(\|\mathbf{x}_i - \mathbf{x}_0\|)}$$
where common weight functions include Gaussian: $w(d) = \exp(-d^2/\sigma^2)$ or inverse distance: $w(d) = 1/(1+d)$.

**Approach 3: Local kernel regression**  
Fit parametric functions (linear, polynomial) within the neighborhood, capturing local trends:
$$y(\mathbf{x}) \approx \beta_0 + \beta_1 \cdot (\mathbf{x} - \mathbf{x}_0) + \ldots \quad \text{within neighborhood}(\mathbf{x}_0)$$
where $\beta$ coefficients are fit using weighted least squares over the local window.

This sliding window methodology transforms the problem from:
- **"Estimate PDF at each isolated bin"** (fails in sparse regions)  
to:
- **"Estimate smooth PDF field using local information"** (succeeds with local smoothness)

### 1.3 Beyond Simple Smoothing: PDF Estimation and Model Factorization

The sliding window approach serves a deeper purpose in the **RootInteractive** framework [[Ivanov et al. 2024, arXiv:2403.19330]](https://arxiv.org/abs/2403.19330): enabling iterative, multidimensional PDF estimation and analytical model validation.

#### 1.3.1 Balanced Semi-Stratified Sampling

To handle massive ALICE data volumes (>100TB/day) while maintaining statistical power across parameter space:

1. **Original data:** Highly unbalanced (exponential/power-law distributions in mass, pT, PID)
2. **Balanced sampling:** Pre-sample using **"balanced semi-stratified sampling"** (density-aware resampling that flattens highly imbalanced distributions such as pT or particle identification, enabling uniform coverage of the full parameter space)
3. **Volume reduction:** 10× to 10^4× reduction (typical: 10^2-10^3) depending on use case
   - Distortion maps: ~10× reduction (need high spatial statistics)
   - Performance parameterization: ~10^3× reduction (broader phase space coverage)
4. **Store weights:** Enable post-hoc reweighting to original distribution

**Example:** For track resolution studies across 5D phase space (pT, η, occupancy, time, PID), sampling from 10^11 tracks to 10^8 events provides sufficient statistics per bin while enabling interactive analysis with <4GB memory footprint.

**Result:** Process 0.01-10% of data with full statistical coverage, enabling iterative analysis and rapid feedback cycles essential for calibration workflows.

#### 1.3.2 Functional Decomposition and Factorization

Real-world calibrations rarely have simple analytical models for full multidimensional behavior. However, we often have models for **normalized deltas** and **factorized components**.

**Example: TPC distortion modeling**
```
Full model (unknown): d(x, y, z, t, φ, rate, ...)
                      
Factorization approach:
1. Extract spatial base map: d₀(x, y, z) [from sliding window fits]
2. Model temporal delta: δd(t) = A·exp(-t/τ₁) + B·exp(-t/τ₂) [analytical]
   - Typical temporal resolution: 5-10 minute averaged maps (90 samples/day)
   - For fast fluctuations: O(1s) resolution requires coarser spatial binning
3. Exploit symmetry: φ-independence for space charge (electric charge accumulation from ionization) effects
4. Rate dependence: Normalize by IDC (Integrator Drift Current, a proxy for detector occupancy and space charge density)

Composed model: d(x,y,z,t,φ,rate) = d₀(x,y,z) · δd(t) · f(IDC) + symmetry checks
```

**Sliding window role:** Extract the non-parametric base functions (d₀) from sparse data, then validate factorization assumptions and fit parametric delta models on normalized residuals.

**Note on RootInteractive:** The RootInteractive tool [[Ivanov et al. 2024, arXiv:2403.19330]](https://arxiv.org/abs/2403.19330) provides interactive visualization and client-side analysis of the extracted aggregated data. Sliding window regression is the *server-side* preprocessing step that prepares binned statistics and fit parameters for subsequent interactive exploration and model validation.

#### 1.3.3 Symmetries, Invariants, and Alarm Systems

After normalization and factorization, physical symmetries should be restored:
- **Temporal invariance:** Corrections stable across runs (after rate normalization)
- **Spatial symmetry:** φ-independence for space charge effects
- **Magnetic field symmetry:** Consistent behavior for ±B fields

**Alarm logic:** If `(data - model) / σ > N` for expected symmetries, either:
- Data quality issue → flag for investigation
- Model inadequacy → symmetry-breaking effect discovered
- Calibration drift → update correction maps

**Sliding window enables:** Compute local statistics needed for σ estimation and symmetry validation across all dimensions.

### 1.4 The Software Engineering Challenge: A Generic Solution

While the statistical methodology is well-established (kernel regression, local polynomial smoothing), applying it to real-world detector calibration requires:

**Dimensional flexibility:**
- Integer bin indices (xBin, y2xBin, z2xBin)
- Float coordinates (time, momentum, angles)
- Mixed types in same analysis
- Dimensions ranging from 3D to 6D+

**Boundary conditions:**
- Spatial boundaries: mirror/truncate/extrapolate
- Periodic dimensions (φ angles): wrap-around
- Physical boundaries: zero padding
- Per-dimension configuration

**Integration with existing tools:**
- Must work with pandas DataFrames (standard scientific Python)
- Leverage existing groupby-regression engines (v4 with Numba JIT)
- Support pre-aggregated data from batch jobs
- Enable client-side interactive analysis (RootInteractive dashboards)

**Performance requirements:**
- Process 405k rows × 5 maps with ±1 window: <1 minute
- Scale to 7M rows × 90 maps: <30 minutes
- Memory efficient: avoid 27-125× expansion where possible
- Parallel execution across cores

**Reusability imperative:**
- One implementation for TPC distortions, particle ID, mass spectra, ...
- User-defined fit functions (linear, polynomial, non-linear, simple statistics)
- Configurable weighting schemes
- Documented, tested, maintainable

**Translating theory into practice:** Translating these statistical concepts into practice requires a software framework that maintains dimensional flexibility while remaining computationally efficient and memory-bounded (<4GB per analysis session). Past C++ and Python implementations demonstrated the value of this approach but had limitations in extensibility and performance (see Section 5 for detailed history). This specification defines requirements for a production-ready, general-purpose solution that addresses these limitations.

### 1.5 Scope and Goals of This Specification

This document defines a **Sliding Window GroupBy Regression** framework that:

1. **Supports arbitrary dimensionality** (3D-6D typical, extensible to higher)
2. **Handles mixed data types** (integer bins, float coordinates, categorical groups)
3. **Flexible window configuration** (per-dimension sizes, asymmetric, distance-based)
4. **Systematic boundary handling** (mirror, truncate, periodic, per-dimension rules)
5. **User-defined aggregations** (linear fits, statistics, custom functions)
6. **Performance at scale** (millions of rows, thousands of bins, <30 min runtime)
7. **Integration with RootInteractive** (pandas I/O, client-side visualization)
8. **Production-quality implementation** (tested, documented, maintainable)

**Primary use cases:**
- **ALICE TPC distortion maps:** Spatial corrections with temporal evolution
- **Performance parameterization:** Resolution and efficiency as functions of kinematic variables
  - Track pT resolution: σ(pT)/pT vs (pT, η, occupancy, time)
  - Track matching resolution and biases
  - V0 reconstruction resolution and biases  
  - PID (Particle Identification) resolution and systematic uncertainties
  - Efficiency maps for various reconstruction algorithms
  - QA variables (χ², cluster counts, dE/dx) across parameter space
  - MC-to-data remapping corrections
- **Particle physics:** Invariant mass spectra in multi-dimensional kinematic bins
- **Generic:** Any binned analysis requiring PDF estimation in high dimensions (3D-6D+)

**Success criteria:**
- Replaces existing C++ implementations with cleaner API
- Enables new analyses previously infeasible (6D+ spaces)
- Reduces analysis time from hours/days to minutes
- Becomes standard tool in ALICE calibration workflow

**Intended audience:**
- ALICE TPC calibration experts (primary)
- Particle physics data analysts (secondary)
- Scientific Python community (general reusability)

**Next steps:** Section 2 describes the representative datasets and validation scenarios that illustrate these concepts with concrete examples from ALICE TPC calibration and performance studies.

---

## 2. Example Data

[To be written in next iteration]

---

## 3. Example Use Cases

[To be written in next iteration]

---

## 4. Goal - Functional Representation

[To be written in next iteration]

---

## 5. Past Implementations

### 5.1 C++ Implementation (2015-2024)

**Overview:** The original sliding window implementation was developed in C++ within the ALICE AliRoot/O2 framework, using N-dimensional histograms as input structures.

**Key features:**
- Multi-dimensional histogram-based approach using ROOT's THnSparse
- Efficient kernel lookups via histogram bin navigation
- Support for various boundary conditions (mirror, truncate, periodic)
- Integrated with ALICE offline analysis framework

**Strengths:**
- Proven in production for TPC calibration (distortion maps, 2015-2024)
- Computationally efficient for large datasets
- Well-tested and reliable

**Limitations:**
- Rigid configuration: adding new fit functions required C++ code changes
- Complex API: required deep knowledge of ROOT histogram internals
- Limited extensibility: difficult to prototype new methods
- Tight coupling to ALICE-specific data structures
- Challenging for non-experts to use or modify

### 5.2 Python Implementation v1 (2024)

**Overview:** Initial Python prototype using DataFrame expansion to aggregate neighboring bins.

**Approach:**
```python
# For ±1 window in 3D:
# Replicate each row to all neighbor combinations
# (xBin±1) × (y2xBin±1) × (z2xBin±1) = 3³ = 27 copies per row
# Then use standard pandas groupby on expanded DataFrame
```

**Strengths:**
- Simple conceptual model
- Leverages existing pandas/numpy ecosystem
- Easy to prototype and modify
- Works with standard groupby-regression tools (v4 engine)

**Limitations:**
- **Memory explosion:** 27× expansion for ±1 window, 125× for ±2 window
- **Performance:** Slow for large datasets due to data replication overhead
- **Scalability:** Infeasible for ±3 windows (343×) or high-dimensional spaces
- Not production-ready for ALICE scale (7M rows × 90 maps × 27 = 17B rows)

### 5.3 Lessons Learned

**From C++ experience:**
- Kernel-based approaches are computationally efficient
- N-dimensional histogram indexing provides fast neighbor lookups
- Flexibility for user-defined fit functions is essential
- API complexity limits adoption and experimentation

**From Python v1 experience:**
- DataFrame-native approach integrates well with scientific Python ecosystem
- Expansion method is intuitive but not scalable
- Need balance between simplicity and performance

**Requirements for this specification:**
- Combine C++ performance with Python flexibility
- Efficient aggregation without full DataFrame expansion
- User-definable fit functions and weighting schemes
- Clean API accessible to non-experts
- Production-scale performance (<4GB memory, <30 min runtime)

---

## 6. Specifications - Requirements

[To be written in next iteration]

---

## References

- Ivanov, M., Ivanov, M., Eulisse, G. (2024). "RootInteractive tool for multidimensional statistical analysis, machine learning and analytical model validation." arXiv:2403.19330v1 [hep-ex]
- [ALICE TPC references to be added]
- [Statistical smoothing references to be added]

---

**End of Section 1 Draft**
