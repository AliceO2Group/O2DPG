# Sliding Window GroupBy Regression - Specification Document

**Authors:** Marian Ivanov (GSI/ALICE), Claude (Anthropic)  
**Reviewers:** GPT-4, Gemini  
**Date:** 2025-10-27  
**Version:** 0.1 (Draft)

---

## 1. Motivation

### 1.1 The Core Challenge: Probability Density Function Estimation in High-Dimensional Spaces

In high-energy physics and detector calibration, we face a fundamental challenge: **estimating probability density functions (PDFs) and their statistical properties** (quantiles, moments, correlations) from data distributed across high-dimensional parameter spaces. This is not merely a function fitting problem—we must characterize the full statistical behavior of observables as they vary across multiple dimensions simultaneously.

**Note:** While examples in this specification are drawn from ALICE tracking and calibration (including TPC distortions, tracking performance, and combined detector calibration), the underlying statistical challenge—estimating local PDFs in high-dimensional sparse data—is generic to many scientific domains including medical imaging, climate modeling, and financial risk analysis.

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
Track segment resolution as function of (pT, η, φ, occupancy, time):
- 5D parameter space: 50 × 40 × 36 × 20 × 100 = 144M bins
- Measurements: TPC-ITS track difference (bias and resolution),
                TPC-vertex (bias and resolution)
- Common approach: TPC-vertex and angular matching for QA parameterization
- Similar challenges: V0 reconstruction, PID (Particle IDentification) resolution
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

**Note on sampling schemes:** For distortion map creation, uniform spatial sampling is under development; current production primarily uses time-based balanced sampling. For performance studies and particle identification, balanced sampling across kinematic variables is standard practice.

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
- Dimensions ranging from 3D to 6D+ (typical use cases)
- **Note:** Actual dimensionality and bin counts depend on use case and memory constraints (e.g., Grid central productions have memory limits affecting maximum binning)

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
- Process 405k rows × 5 maps with ±1 window: <1 minute (typical TPC spatial case)
- Scale to 7M rows × 90 maps: <30 minutes (full temporal evolution)
- Memory efficient: avoid 27-125× expansion where possible; <4GB per session target
- Parallel execution across cores
- **Note:** Specific targets depend on use case, hardware, and dataset characteristics

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
- **ALICE tracking performance:** Combined detector calibration and tracking quality
    - Track segment resolution: TPC-ITS, TPC-vertex matching (bias and resolution)
    - Angular matching and vertex constraints
    - V0 reconstruction resolution and biases
    - PID (Particle Identification) resolution and systematic uncertainties
    - Efficiency maps for various reconstruction algorithms
    - QA variables (χ², cluster counts, dE/dx) across parameter space
    - MC-to-data remapping corrections
- **Future development:** Combined tracking performance parameterization and ALICE calibration integration
- **Particle physics:** Invariant mass spectra in multi-dimensional kinematic bins
- **Generic:** Any binned analysis requiring PDF estimation in high dimensions (3D-6D+)

**Success criteria:**
- Replaces existing C++ implementations with cleaner API
- Enables new analyses previously infeasible (6D+ spaces)
- Reduces analysis time from hours/days to minutes
- Becomes standard tool in ALICE calibration workflow

**Intended audience:**
- ALICE tracking and calibration experts (primary: TPC, ITS, tracking performance)
- Particle physics data analysts (secondary)
- Scientific Python community (general reusability)

**Next steps:** Section 2 describes the representative datasets and validation scenarios that illustrate these concepts with concrete examples from ALICE TPC calibration and performance studies.

---

## 2. Example Data

This section describes representative datasets used to motivate and validate the sliding window regression framework. These examples span ALICE tracking, calibration, and performance studies, illustrating the range of dimensionalities, bin structures, and statistical challenges the framework must address.

### 2.1 Dataset Overview

Three primary dataset categories demonstrate the framework's applicability:

1. **TPC Spatial Distortion Maps** (current test data)
2. **TPC Temporal Evolution** (production scale)
3. **Tracking Performance Parameterization** (multi-dimensional)

Each dataset exhibits the characteristic challenges of high-dimensional sparse data requiring local aggregation through sliding window techniques.

---

### 2.2 Dataset A: TPC Spatial Distortion Maps (Test Data)

**Purpose:** Validate spatial sliding window aggregation with realistic detector calibration data.

**Data source:** ALICE TPC sector 3 distortion corrections from 5 time slices example fordistertion vs integrated digital current (IDC) calibration

#### 2.2.1 Structure

**File:** `tpc_realistic_test.parquet` (14 MB parquet for 1 sector - 5 maps-tome slices for distortion vs curent fits)

**Dimensions:**
```
Rows: 405,423
Columns: O(20)

Spatial binning:
- xBin:    152 bins [0 to 151]  (radial direction in TPC)
- y2xBin:   20 bins [0 to  19]  (pad-row normalized y)
- z2xBin:   28 bins [0 to  27]  (drift-direction normalized z)
- bsec:      1 value [3]         (sector 3 only in test data)


Temporal structure:
- run:            1 unique run
- medianTimeMS:   5 unique time points
- firstTFTime:    5 time slices
```

#### 2.2.2 Target Variables (Fit Targets)

**Distortion corrections (primary):**
- `dX`: Radial distortion [-4.4 to +5.0 cm]
- `dY`: Pad-row direction distortion [-1.4 to +2.0 cm]
- `dZ`: Drift direction distortion [-2.0 to +3.6 cm]

**Derived quantities:**
- `EXYCorr`: Combined XY correction magnitude [-0.84 to +0.89]
- `D3`: 3D distortion magnitude [0.23 to 4.85 cm]

All target variables are fully populated (405,423 non-null values).

#### 2.2.3 Features (Fit Predictors)

**Detector state:**
- `meanIDC`: Mean Integrator Drift Current [mean: 1.89, median: 1.97]
- `medianIDC`: Median IDC [mean: 1.89, median: 1.97]
- `deltaIDC`: IDC variation in respect to fill average 
- `meanCTP`, `medianCTP`: QA variable. -independent current proxy


**Statistics:**
- `entries`: Entries per bin [median: 2840]
- `weight`: Statistical weight

**Quality:**
- `flags`: Quality flags (value: 7 in test data)


**Memory footprint:** using per sector splitting
- In-memory (pandas): 45.6 MB
- Per-row overhead: 113 bytes

#### 2.2.5 Use Case

This dataset validates:
- **Spatial sliding window** aggregation (±1 in xBin, y2xBin, z2xBin)
- **Integer bin indexing** with boundary handling
- **Linear regression** within sliding windows (dX, dY, dZ ~ meanIDC)
- **Multi-target fitting** (simultaneous fits for dX, dY, dZ)


**Expected workflow:**
1. For each center bin (xBin, y2xBin, z2xBin)
2. Aggregate data from ±1 neighbors (3×3×3 = 27 bins)
3. Fit linear model: `dX ~ meanIDC` (and similarly for dY, dZ)
4. Extract coefficients, uncertainties, and diagnostics per center bin
5. Result: Smoothed distortion field with improved statistics

---


### 2.4 Dataset C: Tracking Performance Parameterization

**Purpose:** Multi-dimensional performance metrics requiring combined spatial, kinematic, and temporal aggregation.

#### 2.4.1 Track Segment Resolution
To provide comprehensive tracking performance characterization, 
we analyze track segment residuals and QA variabels  as functions of multiple kinematic and detector conditions.
Varaibles are usualy transmed e.g instead of binnin in pt we use q/pt for better linearity, and to miinmize amout of bins
resp. to get enough statistics per bin.
**Measurement:** TPC-ITS matching and TPC-vertex constraints

**Dimensions:**
```
5D parameter space:
- q/Pt       200 bins [-8 to +8 c/GeV]   (charge over pT)
- η:         20 bins [-1.0 to +1.0]      (pseudorapidity)  
- φ:         180 bins [0 to 2π]           (azimuthal angle)
- sqrt(occupancy): -510 bins               (number of track in TPC volume)
- rate (kHz): 5-10 bins [0 to 50 kHz]      (detector load)

Total bins: 200 × 20 × 180 × 10 × 10 = 144,000,000

```

**Targets:**
- Track segment residuals: mean bias, RMS, quantiles (10%, 50%, 90%)
- Angular matching: Δθ, Δφ at vertex
- DCA (Distance of Closest Approach): XY and Z components
- χ² distributions per track type
- efficinecy 
- PID- dEdx, dEdx per region and per specie




### 2.5 Dataset Comparison Summary 
<!-- MI-SECTION: Note for later review --> To be updated by Claude.

Data volume here is approacimate. Usually I mal limitted by the 2 GBy limit THN sizein ROOT

| **Dataset** | **Dimensions** | **Bins** | **Rows** | **Memory** | **Sparsity** | **Window Type** |
|-------------|---------------|----------|----------|------------|--------------|-----------------|
| **A: TPC Spatial** | 3D (x,y,z) | 85k | 405k | 46 MB | 26% occupied | Integer ±1-2 |
| **B: TPC Temporal** | 4D (x,y,z,t) | 1.5M | 7-10M | 0.8-1.5 GB | 20-30% | Integer + time |
| **C: Track Resolution** | 5D (pT,η,φ,occ,t) | 144M | 100M-1B | 10-100 GB | 50-70% sparse | Float ±1-3 |
| **C: Efficiency** | 4D (pT,η,φ,occ) | 3.2M | 10M-100M | 1-10 GB | 30-50% | Float ±1-2 |
| **C: PID** | 3D (p,dE/dx,occ) | 200k | 1M-10M | 0.1-1 GB | 40-60% | Float ±2-5 |

**Key observations:**
- **Dimensionality:** 3D to 6D (if combining parameters)
- **Bin counts:** 10⁴ to 10⁸ (memory and compute constraints vary)
- **Sparsity:** 20-70% of bins have insufficient individual statistics
- **Window types:** Integer (spatial bins), float (kinematic variables), mixed
- **Memory range:** 50 MB (test) to 100 GB (full production without sampling)

---

### 2.6 Data Characteristics Relevant to Sliding Window Design

#### 2.6.1 Bin Structure Types
<!-- MI-SECTION: Note for later review --> To be updated by Claude.

**Observed in ALICE data:**

1. **Uniform integer grids** (TPC spatial bins)
    - Regular spacing, known bin IDs
    - Efficient neighbor lookup: bin ± 1, ± 2
    - Example: xBin ∈ [0, 151], step=1

2. **Non-uniform float coordinates** (kinematic variables, time)
    - Variable bin widths (e.g., logarithmic pT binning)
    - Neighbors defined by distance, not index
    - Example: pT bins = [0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1.0, ...]

3. **Periodic dimensions** (φ angles)
    - Wrap-around at boundaries: φ=0 ≡ φ=2π
    - Requires special boundary handling

4. **Mixed types** (combined analyses)
    - Spatial (integer) + kinematic (float) + temporal (float)
    - Requires flexible window specification per dimension

#### 2.6.2 Statistical Properties

**From Dataset A analysis:**

```python
# Bin-level statistics (before sliding window):
entries_per_bin = [1, 1, 1, 2, 1, 1, ...]  # median: 1
mean_IDC = [1.89, 1.92, 1.88, ...]         # varies per bin
dX_values = [-2.1, 0.5, -1.8, ...]         # target distortions

# Challenge: Cannot reliably fit dX ~ meanIDC with n=1-2 points per bin
# Solution: Sliding window aggregates 27-125 neighbors → sufficient stats
```

**Statistical needs:**
- **Minimum for mean/median:** ~10 points (robust estimates)
- **Minimum for RMS/quantiles:** ~30 points (stable tail estimates)
- **Minimum for linear fit:** ~50 points (reliable slope, uncertainty)
- **Typical window provides:** 27 (±1 in 3D) to 343 (±3 in 3D) potential bins

**Reality check:** Not all neighbor bins are populated, effective N often 20-60% of theoretical maximum due to sparsity.

#### 2.6.3 Boundary Effects

**Spatial boundaries (TPC geometry):**
- xBin=0: Inner field cage (mirror or truncate)
- xBin=151: Outer field cage (mirror or truncate)
- z2xBin=0,27: Readout planes (asymmetric, truncate)
- 3 internal boundaries (stacks  edges at rows 63,100,...): (non smoothing across)
- φ: Periodic (wrap-around)


**Implications for sliding window:**
- Must support per-dimension boundary rules
- Cannot use one-size-fits-all approach
- Boundary bins have fewer neighbors → adjust weighting or normalization

---

### 2.7 Data Availability and Access for bencmarkings

**Test dataset (Dataset A):**
- File: `benchmarks/data/tpc_realistic_test.parquet` (14 MB)
- Format: Apache Parquet (optimized) or pickle (compatibility)
- Source: ALICE TPC sector 3, 5 time slices, anonymized for testing
- Public: Yes (within O2DPG repository for development and validation)


**Synthetic data generation:**
- For testing and benchmarking: Can generate representative synthetic data
- Preserves statistical structure without real detector specifics
- Script: `benchmarks/data/generate_synthetic_tpc_data.py` (to be added)

---

**Next steps:** Section 3 describes concrete use cases and workflows that leverage these datasets to demonstrate the sliding window framework's capabilities.

---

## 3. Example Use Cases

[To be written in next iteration]

---

## 4. Goal - Functional Representation

[To be written in next iteration]

---

## 5. Past Implementations

### 5.1 C++ Implementation (2015-2024)

**Overview:** The original sliding window implementation was developed in C++ within the ALICE AliRoot framework, 
using N-dimensional histograms as input structures. The code has not yet been ported to the Run 3 O2 framework, 
and until recently it was used for Run 3 data with AliRoot as a side package.

It was used for performance and dE/dx parameterisation, as well as the initial implementation of the TPC distortion 
maps in 2015. Q/q, track delta, and efficiency  variables were grouped into histograms with the same binning. 
Several versions of binning with different granularity and focus were used, in order to bypass the ROOT internal 
limitation of 1 GB.

Detector-based summary binning versions:
* Kinematical variables (q/pt, tgl)
* ~ occupancy
* Phi/sector modulation (90 or 180 bins in the full phi range, or 10–20 bins per sector assuming sector symmetry)


**Key features:**
- Multi-dimensional histogram-based approach using ROOT's THnSparse binned (1GBy limit)
  - O(10) varaiblae types x 5 biining types used (see comment above)  
  - aggregation using smapled data on server (bash parallel comand), or farm if larger production
- Sliding window implmentation as a proposprocessing step together with groupby regression
  - Kernel-based neighbor aggregation using histogram bin indexing
  - In addition to calluating sldiing window statistcs (mean,median, std,mad LTM) of variables  of interest 
      (dEdx,efficency,track deltai) aslo mean of varaibles used for binning (q/pt,eta,phi,occupancy)
  - Weighting schemes: uniform, distance-based (inverse distance, Gaussian)
- User-defined fit functions (linear, polynomial, custom)
- Integrated with ALICE offline analysis framework

#### 5.1 C++ Function Signature

```C++
/// Create list of histograms specified by selection
/// Should be rough equivalent of the "ALICE train" TTree->Draw();
///  a.) Data are read only once
///  b.) values expression are reused (evaluated only once)
///  c.) Axis labelling and names of variables extracted from the tree metadata (.AxisTitle)
/// * default cut
///   * default selection applied common for all histograms (can be empty)
///
/// * hisString : - semicolomn separated string
///   * his0;his1; ...; hisN
/// * histogram syntax:
///    * var0:var1:...:<#weight>>>hisName(bins0,min0,max0,bins1,min0,min, minValue,maxValue)
///    * Syntax:
///      * vari are histogramming expression
///      * weight (or cut) entry is optional
///        * default cut is always applied, weight is applied on top
///    * ranges syntax:
///      *  nbins,max,min where max and min are double or format strings
///        * in case format string % specified using (Fraction, mean,meanFraction, rms, rmsFraction)
///          *  %fraction.sigma
///          *  #cumulant
///          *  range for bin content can be specified in the same format (by default is not set)
/*!
##### CPU time to process one histogram or set of histograms (in particular case of esdTrack queries) is the same - and it is determined (90 %) by tree->GetEntry
\code
  THn * his0= (THn*)hisArray->At(0);
  his0->Projection(0)->Draw("");
  tree->SetLineColor(2);
  TStopwatch timer; tree->Draw("esdTrack.Pt()","(esdTrack.fFlags&0x40)>0&&esdTrack.fTPCncls>70","same",60000); timer.Print();
\endcode
*/

/// \param tree         - input tree
/// \param hisString    - selection string
/// \param defaultCut   - default selection applied common for all histograms (can be empty)
/// \param firstEntry   - first entry to process
/// \param lastEntry    - last entry to process
/// \param chunkSize    - chunk size
/// \param verbose      - verbosity
/// \return             - TObjArray of N-dimensional histograms
/*!
#### Example usage:
\code
    chunkSize=10000;
    verbose=7;
    chinput=gSystem->ExpandPathName("$NOTES/JIRA/PWGPP-227/data/2016/LHC16t/000267161/pass1_CENT_wSDD/filteredLocal.list");
    TString defaultCut="esdTrack.fTPCncls>70";
    TTree *tree=(TTree*)AliXRDPROOFtoolkit::MakeChain(chinput, "highPt", 0, 1000000000,0);
    TString hisString="";
    hisString+="esdTrack.Pt():#esdTrack.fTPCncls>70>>hisPtAll(100,0,30);";
    hisString+="esdTrack.GetAlpha():#esdTrack.fTPCncls>70>>hisAlpha(90,-3.2,3.2);";
    hisString+="esdTrack.GetTgl():#esdTrack.fTPCncls>70>>hisTgl(20,-1.2,1.2);";
    hisString+="esdTrack.Pt():esdTrack.GetAlpha():esdTrack.GetTgl():#esdTrack.fTPCncls>70>>hisPtPhiThetaAll(100,0,30,90,-3.2,3.2,20,-1.2,1.2);";
    hisString+="esdTrack.Pt():#(esdTrack.fFlags&0x4)>0>>hisPtITS(100,1,10);";
    hisString+="esdTrack.fIp.Pt():#(esdTrack.fFlags&0x4)>0>>hisPtTPCOnly(100,1,10);";
    TStopwatch timer; hisArray = AliTreePlayer::MakeHistograms(tree, hisString, "(esdTrack.fFlags&0x40)>0&&esdTrack.fTPCncls>70",0,60000,100000); timer.Print();
\endcode
 */
TObjArray  * AliTreePlayer::MakeHistograms(TTree * tree, TString hisString, TString defaultCut, Int_t firstEntry, Int_t lastEntry, Int_t chunkSize, Int_t verbose){
```
```C++
/// TStatToolkit::MakePDFMap function to calculate statistics form the N dimensnal PDF map
/// Original implementation - a copy of the MakeDistortionMapFast
/// \param histo              -  input n dimsnional histogram
/// \param pcstream           -  output stream to store tree with PDF statistic maps
/// \param projectionInfo     -
/// \param options            - option - parameterize statistic to extract
/// \param verbose            - verbosity of extraction
/// Example:
/// options["exportGraph"]="1";
///  options["exportGraphCumulative"]="1";
///  options["LTMestimators"]="0.6:0.5:0.4";
//  options["LTMFitRange"]="0.6:5:1";
void TStatToolkit::MakePDFMap(THnBase *histo, TTreeSRedirector *pcstream, TMatrixD &projectionInfo, std::map<std::string, std::string> pdfOptions, Int_t verbose)


```


**Strengths:**
- Proven in production for globale trackin and calibration QA
- Computationally efficient for large datasets
- Well-tested and reliable
- Used for expert QAs

**Limitations:**
- Tight coupling with ROOT - addopting ROT string based configuration for describing histograms
- Using C++11 - not easy configuration - preferied not to rely on templates
- Rigid configuration: string based API to define histograms and mapping (in pythyo using dictionaries)
- Limited extensibility: difficult to add new fit functions
- Relying on the AliRoot framework - not directly usable in O2 or scientific Python ecosystem




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
- Works with standard groupby-regression tools 

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




## 6. Specifications - Requirements

[To be written in next iteration]

---

## References

- Ivanov, M., Ivanov, M., Eulisse, G. (2024). "RootInteractive tool for multidimensional statistical analysis, machine learning and analytical model validation." arXiv:2403.19330v1 [hep-ex]
- [ALICE TPC references to be added]
- [Statistical smoothing references to be added]

---

**End of Section 1 Draft**